"""Streaming chat over WebSocket (`WS /ws/chat`).

Protocol
--------
Client → server (JSON):
    {"type": "message", "session_id": <str|null>, "message": <str>,
     "input_type": "text"|"voice"}

Server → client (JSON), per turn:
    {"type": "session", "session_id": <str>}
    {"type": "token",   "token": <str>}          # repeated
    {"type": "done",    "message_id", "latency_ms", "sources": [...]}
    {"type": "error",   "code", "message"}        # on failure

A fresh DB session (and transaction) is opened per message and committed when
the turn completes, so a long-lived socket doesn't hold one transaction open.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import ws_active_connections
from app.db.session import get_sessionmaker
from app.services.factory import build_conversation_manager

router = APIRouter()
logger = get_logger("voiceai.ws.chat")


async def _run_turn(websocket: WebSocket, payload: dict) -> None:
    message = (payload.get("message") or "").strip()
    if not message:
        await websocket.send_json(
            {"type": "error", "code": "empty_message", "message": "Message is required."}
        )
        return

    settings = get_settings()
    sessionmaker = get_sessionmaker()
    done_event: dict | None = None
    try:
        async with sessionmaker() as db:
            manager = build_conversation_manager(db, settings)
            async for event in manager.stream(
                session_id=payload.get("session_id"),
                message=message,
                input_type=payload.get("input_type", "text"),
                user_ref=payload.get("user_ref"),
                language=payload.get("language"),
            ):
                # Hold back "done" until the turn is durably committed below,
                # so the client never learns of completion before it's saved
                # (and teardown can't race with the DB commit).
                if event.get("type") == "done":
                    done_event = event
                else:
                    await websocket.send_json(event)
            await db.commit()
    except Exception:  # noqa: BLE001 - surface a clean error to the client
        logger.exception("Chat turn failed")
        await websocket.send_json(
            {"type": "error", "code": "internal_error",
             "message": "Failed to process message."}
        )
        return

    if done_event is not None:
        await websocket.send_json(done_event)


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    ws_active_connections.labels(endpoint="chat").inc()
    try:
        # iter_json() yields until the client disconnects, then ends cleanly
        # (it swallows WebSocketDisconnect), so the handler always unwinds.
        async for payload in websocket.iter_json():
            if payload.get("type") == "message":
                await _run_turn(websocket, payload)
            else:
                await websocket.send_json(
                    {"type": "error", "code": "unknown_type",
                     "message": "Expected {'type': 'message', ...}"}
                )
    except WebSocketDisconnect:
        logger.debug("Chat WebSocket disconnected")
    finally:
        ws_active_connections.labels(endpoint="chat").dec()
