"""User preference schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PreferencesUpsertRequest(BaseModel):
    user_ref: str = Field(min_length=1, max_length=128)
    theme: str | None = Field(default=None, pattern=r"^(light|dark)$")
    language: str | None = Field(default=None, max_length=16)
    voice_enabled: bool | None = None
    tts_voice: str | None = Field(default=None, max_length=64)


class PreferencesResponse(BaseModel):
    user_ref: str
    theme: str
    voice_enabled: bool
    tts_voice: str | None
    language: str
    updated_at: datetime
