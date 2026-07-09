"""Session schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.db.models.enums import Channel


class SessionCreateRequest(BaseModel):
    channel: Channel = Channel.TEXT
    user_ref: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    channel: str
    created_at: datetime
