"""Analytics event model (voiceai.analytics) — feeds the future dashboard."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, fk_target
from app.db.types import GUID, new_uuid


class AnalyticsEvent(Base, TimestampMixin):
    """A generic analytics event (latency, errors, usage, custom)."""

    __tablename__ = "analytics"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    session_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey(fk_target("sessions.id"), ondelete="SET NULL"),
        nullable=True, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
