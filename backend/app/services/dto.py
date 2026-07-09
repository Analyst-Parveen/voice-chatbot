"""Internal data-transfer objects for the service layer.

These are plain dataclasses used *between* services (not exposed over HTTP —
that's what ``app/schemas`` is for). Keeping them separate means the service
layer never depends on FastAPI or Pydantic request models.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    """A single conversation turn used to build LLM context."""

    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class RetrievedChunk:
    """A knowledge chunk returned by RAG retrieval."""

    chunk_id: str
    source: str
    score: float
    text: str


@dataclass
class LLMRequest:
    """Everything the LLM needs to answer one turn."""

    user_message: str
    system: str = ""
    history: list[ChatMessage] = field(default_factory=list)
    context: str = ""


@dataclass
class STTResult:
    """Output of speech-to-text."""

    text: str
    language: str | None = None


@dataclass
class TurnResult:
    """The outcome of a completed conversation turn."""

    session_id: str
    message_id: str
    answer: str
    sources: list[RetrievedChunk]
    latency_ms: int
