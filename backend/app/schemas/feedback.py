"""Feedback schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models.enums import Rating


class FeedbackRequest(BaseModel):
    message_id: str
    rating: Rating
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    id: str
    status: str = "recorded"
