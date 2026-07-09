"""Stub service implementations (RUN_MODE=stub).

These let the entire app — chat flow, streaming, WebSockets, persistence — be
built and tested with zero AI load on a low-config PC. They implement the same
interfaces as the real services, so Phases 6–7 drop in faster-whisper, Piper,
Ollama, and Qdrant with no changes to callers.
"""

from __future__ import annotations

import io
import re
import wave
from collections.abc import AsyncIterator

from app.services.dto import LLMRequest, RetrievedChunk, STTResult

# Split into word-plus-trailing-whitespace tokens so "".join(tokens) == text.
_TOKEN_RE = re.compile(r"\S+\s*")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


class StubLLMService:
    """Echo 'LLM' that streams a canned response. No model is loaded."""

    def _answer(self, request: LLMRequest) -> str:
        context_note = " (with retrieved context)" if request.context else ""
        return (
            f'You said: "{request.user_message}".{context_note} '
            "This is a stub response — the real Qwen2.5 model is wired in Phase 7."
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        for token in _tokenize(self._answer(request)):
            yield token

    async def complete(self, request: LLMRequest) -> str:
        return self._answer(request)


class StubRAGService:
    """Returns no knowledge chunks (no vector DB in stub mode)."""

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        return []

    def build_context(self, chunks: list[RetrievedChunk]) -> str:
        return "\n\n".join(f"[{c.source}] {c.text}" for c in chunks)


class StubSTTService:
    """Fake transcription — returns a fixed phrase regardless of audio."""

    async def transcribe(self, audio: bytes, language: str | None = None) -> STTResult:
        return STTResult(text="(stub transcription) hello", language=language or "en")


class StubTTSService:
    """Fake synthesis — returns a short silent but VALID WAV clip.

    Real audio bytes (rather than empty) let the voice pipeline and the frontend
    audio player be exercised end-to-end in stub mode without Piper.
    """

    def _silence_wav(self, seconds: float = 0.15, rate: int = 16000) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(b"\x00\x00" * int(rate * seconds))
        return buf.getvalue()

    async def synthesize(self, text: str) -> bytes:
        return self._silence_wav() if text.strip() else b""
