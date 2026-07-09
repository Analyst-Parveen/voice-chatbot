"""User feedback model (voiceai.feedback)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, fk_target
from app.db.types import GUID, new_uuid


class Feedback(Base, TimestampMixin):
    """Thumbs up/down (plus optional comment) on an assistant message."""

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    message_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey(fk_target("messages.id"), ondelete="CASCADE"),
        nullable=False, index=True,
    )
    rating: Mapped[str] = mapped_column(String(8), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
