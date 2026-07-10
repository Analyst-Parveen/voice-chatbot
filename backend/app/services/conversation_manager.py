"""ConversationManager — orchestrates a single conversation turn.

This is the heart of the service layer. It ties together memory (SQL), RAG
retrieval, prompt building, the LLM, and validation, and is agnostic to whether
those are stubs or real implementations. It exposes two paths that share the
same preparation and finalization so streamed and non-streamed answers are
always produced identically:

- :meth:`handle` — non-streaming (used by ``POST /api/chat``)
- :meth:`stream` — token streaming (used by ``WS /ws/chat``)

The golden rule (displayed text == spoken text) is preserved: the final answer
string is computed once and both persisted and returned/emitted verbatim.
"""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.core.config import Settings
from app.core.metrics import record_turn
from app.db.models.enums import Channel, InputType
from app.rag.prompt_builder import build_system_prompt, detect_script_hint, wrap_user_message
from app.services.cache import AnswerCache
from app.services.dto import ChatMessage, LLMRequest, RetrievedChunk, TurnResult
from app.services.hindi_translator import (
    is_hindi_mode,
    should_translate_to_hindi,
    translate_to_hindi,
)
from app.services.interfaces import LLMService, RAGService
from app.services.memory_service import MemoryService
from app.services.telemetry_service import TelemetryService
from app.services.starter_faqs import lookup_starter_answer
from app.services.validation_service import FALLBACK_MESSAGE, hindi_fallback_message, ValidationService

SYSTEM_PROMPT = build_system_prompt()  # default; per-turn language overrides in _prepare

# Split a cached answer back into word-sized tokens (whitespace preserved) so a
# cache hit streams and speaks exactly like a freshly generated answer.
_REPLAY_TOKEN = re.compile(r"\S+\s*")


@dataclass
class _PreparedTurn:
    session_id: str
    request: LLMRequest
    chunks: list[RetrievedChunk]
    input_type: str
    started: float
    user_ref: str | None = None
    language: str | None = None
    client_ip: str | None = None


class ConversationManager:
    def __init__(
        self,
        *,
        memory: MemoryService,
        llm: LLMService,
        rag: RAGService,
        validation: ValidationService,
        telemetry: TelemetryService,
        settings: Settings,
        cache: AnswerCache | None = None,
    ) -> None:
        self._memory = memory
        self._llm = llm
        self._rag = rag
        self._validation = validation
        self._telemetry = telemetry
        self._settings = settings
        self._cache = cache

    # ---- Shared steps -------------------------------------------------

    async def _prepare(
        self,
        *,
        session_id: str | None,
        message: str,
        input_type: str,
        user_ref: str | None,
        language: str | None = None,
        client_ip: str | None = None,
        skip_rag: bool = False,
    ) -> _PreparedTurn:
        started = time.perf_counter()
        channel = Channel.VOICE.value if input_type == InputType.VOICE.value else Channel.TEXT.value

        session = await self._memory.get_or_create_session(
            session_id, channel=channel, user_ref=user_ref
        )
        await self._memory.add_user_message(session.id, message, input_type)

        history = await self._memory.recent_context(session.id, limit=10)
        chunks = [] if skip_rag else await self._rag.retrieve(message)
        context = self._rag.build_context(chunks)

        request = LLMRequest(
            user_message=wrap_user_message(message, language),
            system=build_system_prompt(
                language,
                detect_script_hint(message, language) if not is_hindi_mode(language) else None,
            ),
            history=self._exclude_last_user(history, message),
            context=context,
        )
        return _PreparedTurn(
            session_id=session.id, request=request, chunks=chunks,
            input_type=input_type, started=started,
            user_ref=user_ref, language=language, client_ip=client_ip,
        )

    @staticmethod
    def _exclude_last_user(history: list[ChatMessage], current: str) -> list[ChatMessage]:
        """Drop the just-persisted user message from the context history."""
        if history and history[-1].role == "user" and history[-1].content == current:
            return history[:-1]
        return history

    async def _finalize(
        self, prepared: _PreparedTurn, answer: str, *, used_fallback: bool = False
    ) -> TurnResult:
        latency_ms = int((time.perf_counter() - prepared.started) * 1000)
        message = await self._memory.add_assistant_message(
            prepared.session_id, answer, prepared.input_type, latency_ms
        )
        grounded_ids = {
            c.chunk_id for c in prepared.chunks if self._validation.is_grounded(c)
        }
        await self._memory.add_retrievals(message.id, prepared.chunks, grounded_ids)
        await self._memory.touch(prepared.session_id)
        record_turn(
            prepared.input_type,
            fallback=used_fallback,
            latency_ms=latency_ms,
        )
        await self._telemetry.record_chat_turn(
            session_id=prepared.session_id,
            message_id=message.id,
            user_ref=prepared.user_ref,
            language=prepared.language,
            input_type=prepared.input_type,
            latency_ms=latency_ms,
            chunk_count=len(prepared.chunks),
            used_fallback=used_fallback,
            client_ip=prepared.client_ip,
        )
        return TurnResult(
            session_id=prepared.session_id,
            message_id=message.id,
            answer=answer,
            sources=prepared.chunks,
            latency_ms=latency_ms,
        )

    async def _localize_answer(
        self,
        english: str,
        *,
        language: str | None,
        user_message: str,
        used_fallback: bool,
    ) -> str:
        """Convert English LLM output to fluent Hindi when Hindi mode is active."""
        if used_fallback and is_hindi_mode(language):
            return hindi_fallback_message(devanagari=True)
        if should_translate_to_hindi(language, english):
            return await translate_to_hindi(
                english, self._llm, user_question=user_message
            )
        return english

    # ---- Public API ---------------------------------------------------

    async def handle(
        self,
        *,
        session_id: str | None,
        message: str,
        input_type: str = InputType.TEXT.value,
        user_ref: str | None = None,
        language: str | None = None,
        client_ip: str | None = None,
    ) -> TurnResult:
        """Run a full turn and return the result (non-streaming)."""
        canned = lookup_starter_answer(message, language)
        prepared = await self._prepare(
            session_id=session_id, message=message,
            input_type=input_type, user_ref=user_ref, language=language,
            client_ip=client_ip, skip_rag=canned is not None,
        )
        if canned is not None:
            return await self._finalize(prepared, canned, used_fallback=False)

        fallback = hindi_fallback_message(devanagari=True) if is_hindi_mode(language) else FALLBACK_MESSAGE
        if not self._validation.should_answer(prepared.chunks):
            return await self._finalize(prepared, fallback, used_fallback=True)

        chunk_ids = [c.chunk_id for c in prepared.chunks]
        cached = await self._cache.get(message, chunk_ids, language) if self._cache else None
        if cached is not None:
            return await self._finalize(prepared, cached, used_fallback=False)

        raw = await self._llm.complete(prepared.request)
        english = self._validation.finalize_answer(raw, prepared.chunks)
        used_fallback = english.strip() == FALLBACK_MESSAGE
        answer = await self._localize_answer(
            english,
            language=language,
            user_message=message,
            used_fallback=used_fallback,
        )
        if self._cache:
            await self._cache.set(message, chunk_ids, language, answer)
        return await self._finalize(prepared, answer, used_fallback=used_fallback)

    async def stream(
        self,
        *,
        session_id: str | None,
        message: str,
        input_type: str = InputType.TEXT.value,
        user_ref: str | None = None,
        language: str | None = None,
        client_ip: str | None = None,
    ) -> AsyncIterator[dict]:
        """Run a full turn, yielding events for a WebSocket client.

        Events: ``{"type": "session", "session_id"}`` →
        ``{"type": "token", "token"}`` (repeated) →
        ``{"type": "done", "message_id", "latency_ms", "sources"}``.
        """
        canned = lookup_starter_answer(message, language)
        prepared = await self._prepare(
            session_id=session_id, message=message,
            input_type=input_type, user_ref=user_ref, language=language,
            client_ip=client_ip, skip_rag=canned is not None,
        )
        fallback = hindi_fallback_message(devanagari=True) if is_hindi_mode(language) else FALLBACK_MESSAGE
        yield {"type": "session", "session_id": prepared.session_id}

        if canned is not None:
            for m in _REPLAY_TOKEN.finditer(canned):
                yield {"type": "token", "token": m.group(0)}
            result = await self._finalize(prepared, canned, used_fallback=False)
            yield {
                "type": "done",
                "message_id": result.message_id,
                "latency_ms": result.latency_ms,
                "sources": [
                    {"chunk_id": c.chunk_id, "source": c.source, "score": c.score}
                    for c in result.sources
                ],
            }
            return

        # Grounding gate BEFORE streaming, so what we stream equals what we store.
        if not self._validation.should_answer(prepared.chunks):
            for m in _REPLAY_TOKEN.finditer(fallback):
                yield {"type": "token", "token": m.group(0)}
            result = await self._finalize(prepared, fallback, used_fallback=True)
        else:
            chunk_ids = [c.chunk_id for c in prepared.chunks]
            cached = (
                await self._cache.get(message, chunk_ids, language) if self._cache else None
            )
            if cached is not None:
                # Cache hit: replay the stored answer as tokens (identical text).
                for m in _REPLAY_TOKEN.finditer(cached):
                    yield {"type": "token", "token": m.group(0)}
                result = await self._finalize(prepared, cached, used_fallback=False)
            else:
                buffer: list[str] = []
                stream_live = not is_hindi_mode(language)
                async for token in self._llm.stream(prepared.request):
                    buffer.append(token)
                    if stream_live:
                        yield {"type": "token", "token": token}
                english = "".join(buffer)
                english = self._validation.finalize_answer(english, prepared.chunks)
                used_fallback = english.strip() == FALLBACK_MESSAGE
                answer = await self._localize_answer(
                    english,
                    language=language,
                    user_message=message,
                    used_fallback=used_fallback,
                )
                if self._cache:
                    await self._cache.set(message, chunk_ids, language, answer)
                if not stream_live:
                    for m in _REPLAY_TOKEN.finditer(answer):
                        yield {"type": "token", "token": m.group(0)}
                result = await self._finalize(prepared, answer, used_fallback=used_fallback)

        yield {
            "type": "done",
            "message_id": result.message_id,
            "latency_ms": result.latency_ms,
            "sources": [
                {"chunk_id": c.chunk_id, "source": c.source, "score": c.score}
                for c in result.sources
            ],
        }
