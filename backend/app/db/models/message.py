"""Conversation message model (voiceai.messages).

``content`` is the final answer text — the exact string that was both displayed
on screen and spoken by TTS (the identical-text-and-voice rule).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, fk_target
from app.db.types import GUID, new_uuid

if TYPE_CHECKING:
    from app.db.models.session import Session


class Message(Base, TimestampMixin):
    """One message in a session (user, assistant, or system)."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey(fk_target("sessions.id"), ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    input_type: Mapped[str] = mapped_column(String(16), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    session: Mapped["Session"] = relationship(back_populates="messages")
