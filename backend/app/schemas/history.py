"""Conversation history schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    input_type: str
    created_at: datetime
    latency_ms: int | None = None


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageOut]
    total: int
    limit: int
    offset: int
