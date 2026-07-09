"""Service interfaces (Protocols).

The service layer depends on these abstractions, never on concrete
implementations. ``RUN_MODE`` decides which implementation is bound at runtime
(stub now; real faster-whisper/Piper/Ollama/Qdrant in Phases 6–7). Because
everything is typed against these Protocols, swapping implementations requires
no changes to the ConversationManager or the API layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.services.dto import LLMRequest, RetrievedChunk, STTResult


@runtime_checkable
class LLMService(Protocol):
    """Large language model text generation."""

    def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Yield answer tokens as they are generated."""
        ...

    async def complete(self, request: LLMRequest) -> str:
        """Return the full answer (non-streaming)."""
        ...


@runtime_checkable
class RAGService(Protocol):
    """Retrieval-augmented generation: fetch grounding context."""

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        """Return the most relevant knowledge chunks for a query."""
        ...

    def build_context(self, chunks: list[RetrievedChunk]) -> str:
        """Assemble retrieved chunks into a context string for the prompt."""
        ...


@runtime_checkable
class STTService(Protocol):
    """Speech-to-text."""

    async def transcribe(self, audio: bytes, language: str | None = None) -> STTResult:
        ...


@runtime_checkable
class TTSService(Protocol):
    """Text-to-speech. Speaks the exact answer string (identical text & voice)."""

    async def synthesize(self, text: str) -> bytes:
        ...
