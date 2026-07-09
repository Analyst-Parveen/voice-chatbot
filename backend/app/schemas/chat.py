"""Chat request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models.enums import InputType


class Source(BaseModel):
    """A knowledge source that grounded the answer."""

    chunk_id: str
    source: str
    score: float


class ChatRequest(BaseModel):
    session_id: str | None = Field(
        default=None, description="Existing session id; omit to start a new session."
    )
    message: str = Field(min_length=1, max_length=4000)
    input_type: InputType = InputType.TEXT


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    sources: list[Source] = Field(default_factory=list)
    latency_ms: int
