"""Retrieval audit model (voiceai.retrievals).

Records which knowledge chunks grounded each assistant answer — essential for
the anti-hallucination contract and for debugging RAG quality.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, fk_target
from app.db.types import GUID, new_uuid


class Retrieval(Base, TimestampMixin):
    """A single retrieved chunk considered for an assistant message."""

    __tablename__ = "retrievals"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    message_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey(fk_target("messages.id"), ondelete="CASCADE"),
        nullable=False, index=True,
    )
    chunk_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
