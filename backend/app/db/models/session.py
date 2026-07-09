"""Conversation session model (voiceai.sessions)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, utcnow
from app.db.models.enums import Channel
from app.db.types import GUID, new_uuid

if TYPE_CHECKING:
    from app.db.models.message import Message


class Session(Base, TimestampMixin):
    """A single conversation session (voice or text), tied to an optional user."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    # Links to the existing website user once auth is wired (nullable = anonymous).
    user_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(16), default=Channel.TEXT.value, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    # DB column is "metadata"; Python attribute is "meta" (metadata is reserved).
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
