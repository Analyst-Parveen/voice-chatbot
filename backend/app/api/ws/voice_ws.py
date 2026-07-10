"""Voice WebSocket (`WS /ws/voice`) — full spoken-conversation pipeline.

Flow per turn:
    client streams mic audio → STT (faster-whisper) → transcript →
    ConversationManager (RAG + LLM, streamed) → text tokens streamed to UI →
    Piper TTS per sentence → audio chunks streamed back → done.

Protocol
--------
Client → server:
    {"type": "audio_start", "session_id": <str|null>}
    <binary audio frames…>
    {"type": "audio_end"}                     # triggers a turn
    {"type": "message", "session_id", "message"}   # text path (also spoken)
    {"type": "interrupt"}                     # barge-in: stop generating/speaking

Server → client:
    {"type": "info", "message"}
    {"type": "transcript", "text"}            # recognized speech
    {"type": "session", "session_id"}
    {"type": "token", "token"}                # streamed answer text
    {"type": "audio", "data": <base64 wav>, "mime": "audio/wav"}
    {"type": "done", "message_id", "latency_ms", "sources"}
    {"type": "error", "code", "message"}

Barge-in is cooperative: an ``interrupt`` sets an event that the turn checks
between tokens and sentences, so it stops promptly and the partial turn is
discarded (not committed). The **identical text & voice** rule holds: TTS speaks
exactly the tokens that were displayed — the spoken sentences concatenate to the
displayed answer verbatim.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import ws_active_connections
from app.db.session import get_sessionmaker
from app.services.factory import (
    build_conversation_manager,
    get_stt_service,
    get_tts_for_language,
)
from app.services.telemetry_service import TelemetryService

router = APIRouter()
logger = get_logger("voiceai.ws.voice")

_SENTENCE_END = re.compile(r"(?:[.!?]['\")\]]?|[\u0964\u0965])\s")


def _client_ip(websocket: WebSocket) -> str | None:
    return websocket.client.host if websocket.client else None


async def _run_and_speak(
    websocket: WebSocket,
    *,
    session_id: str | None,
    message: str,
    input_type: str,
    interrupt: asyncio.Event,
    user_ref: str | None = None,
    language: str | None = None,
    client_ip: str | None = None,
) -> None:
    """Run one turn and emit each sentence's TEXT + AUDIO together.

    Falls back to text-only token streaming when TTS is unavailable so the
    client never hangs in a loading state.
    """
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    done_event: dict | None = None
    tts = None
    try:
        tts = get_tts_for_language(settings, language)
    except Exception:
        logger.warning("TTS unavailable — streaming text only for this turn")

    async def say(text: str) -> None:
        audio = b""
        if tts is not None:
            try:
                audio = await tts.synthesize(text)
            except Exception:
                logger.warning("TTS synthesis failed for sentence")
        await websocket.send_json({
            "type": "say",
            "seq": 0,
            "text": text,
            "audio": base64.b64encode(audio).decode("ascii") if audio else "",
            "mime": "audio/wav",
        })

    try:
        async with sessionmaker() as db:
            manager = build_conversation_manager(db, settings)
            async for event in manager.stream(
                session_id=session_id, message=message, input_type=input_type,
                user_ref=user_ref, language=language, client_ip=client_ip,
            ):
                if interrupt.is_set():
                    await db.rollback()
                    await websocket.send_json({"type": "info", "message": "interrupted"})
                    return

                etype = event.get("type")
                if etype == "token":
                    if tts is None:
                        await websocket.send_json(event)
                        continue
                    sentence_buf = getattr(_run_and_speak, "_buf", "")
                    sentence_buf += event["token"]
                    _run_and_speak._buf = sentence_buf  # type: ignore[attr-defined]
                    while (m := _SENTENCE_END.search(sentence_buf)) and not interrupt.is_set():
                        cut = m.end()
                        await say(sentence_buf[:cut])
                        sentence_buf = sentence_buf[cut:]
                    _run_and_speak._buf = sentence_buf  # type: ignore[attr-defined]
                elif etype == "session":
                    await websocket.send_json(event)
                elif etype == "done":
                    done_event = event

            if tts is not None:
                trailing = getattr(_run_and_speak, "_buf", "")
                if trailing.strip() and not interrupt.is_set():
                    await say(trailing)
                _run_and_speak._buf = ""  # type: ignore[attr-defined]

            if interrupt.is_set():
                await db.rollback()
                return
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Voice turn failed")
        await websocket.send_json(
            {"type": "error", "code": "internal_error", "message": "Voice turn failed."}
        )
        return

    if done_event is not None and not interrupt.is_set():
        await websocket.send_json(done_event)


async def _process_audio(
    websocket: WebSocket, audio: bytes, session_id: str | None,
    user_ref: str | None, interrupt: asyncio.Event,
    *, transcribe_only: bool = False, language: str | None = None,
    stt_language: str | None = None, client_ip: str | None = None,
) -> None:
    settings = get_settings()
    stt = get_stt_service(settings)
    result = await stt.transcribe(audio, language=stt_language)
    text = result.text.strip()
    if not text:
        await websocket.send_json({"type": "info", "message": "No speech detected."})
        return
    await websocket.send_json({"type": "transcript", "text": text})
    if transcribe_only:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            await TelemetryService(db).record_voice_transcript(
                session_id=session_id,
                text_length=len(text),
                stt_language=stt_language,
                user_ref=user_ref,
            )
            await db.commit()
        return
    await _run_and_speak(
        websocket, session_id=session_id, message=text, input_type="voice",
        interrupt=interrupt, user_ref=user_ref, language=language, client_ip=client_ip,
    )


@router.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    ws_active_connections.labels(endpoint="voice").inc()
    await websocket.send_json({"type": "info", "message": "voice ready"})

    buffer = bytearray()
    session_id: str | None = None
    user_ref: str | None = None
    language: str | None = None
    stt_language: str | None = None
    transcribe_only = False
    interrupt = asyncio.Event()
    task: asyncio.Task | None = None

    def busy() -> bool:
        return task is not None and not task.done()

    async def _run_task(coro) -> None:
        try:
            await coro
        except Exception:  # noqa: BLE001
            logger.exception("Voice task failed")
            await websocket.send_json(
                {"type": "error", "code": "internal_error", "message": "Voice turn failed."}
            )

    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break

            if msg.get("bytes") is not None:
                buffer.extend(msg["bytes"])
                continue

            text = msg.get("text")
            if text is None:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue

            mtype = data.get("type")
            if mtype == "audio_start":
                buffer.clear()
                interrupt.clear()
                session_id = data.get("session_id", session_id)
                user_ref = data.get("user_ref", user_ref)
                language = data.get("language", language)
                stt_language = data.get("stt_language", stt_language)
                transcribe_only = bool(data.get("transcribe_only"))
            elif mtype == "audio_end":
                if busy() and not transcribe_only:
                    continue
                interrupt.clear()
                audio = bytes(buffer)
                buffer.clear()
                only = transcribe_only
                stt = stt_language
                transcribe_only = False
                stt_language = None
                task = asyncio.create_task(
                    _run_task(_process_audio(
                        websocket, audio, session_id, user_ref, interrupt,
                        transcribe_only=only, language=language,
                        stt_language=stt,
                        client_ip=_client_ip(websocket),
                    ))
                )
            elif mtype == "message":
                if busy():
                    continue
                message = (data.get("message") or "").strip()
                if not message:
                    continue
                interrupt.clear()
                session_id = data.get("session_id", session_id)
                user_ref = data.get("user_ref", user_ref)
                language = data.get("language", language)
                task = asyncio.create_task(
                    _run_task(_run_and_speak(
                        websocket,
                        session_id=session_id,
                        message=message,
                        input_type=data.get("input_type", "voice"),
                        interrupt=interrupt,
                        user_ref=user_ref,
                        language=language,
                        client_ip=_client_ip(websocket),
                    ))
                )
            elif mtype == "interrupt":
                interrupt.set()
    except WebSocketDisconnect:
        logger.debug("Voice WebSocket disconnected")
    finally:
        interrupt.set()
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        ws_active_connections.labels(endpoint="voice").dec()
