"""User preference model (voiceai.user_preferences)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.db.types import GUID, new_uuid


class UserPreference(Base):
    """Per-user UI/voice preferences (theme, TTS voice, language)."""

    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    user_ref: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    theme: Mapped[str] = mapped_column(String(16), default="light", nullable=False)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tts_voice: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
