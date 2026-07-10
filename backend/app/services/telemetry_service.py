"""Persist analytics, user preferences, and audit logs during normal app flows.

These tables power a future admin dashboard. Rows are written in the same DB
transaction as the action they describe (chat turn, session clear, feedback).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalyticsEvent, AuditLog, UserPreference
from app.db.repositories import (
    AnalyticsRepository,
    AuditLogRepository,
    UserPreferenceRepository,
)

# Maps widget / API language labels to DB codes (user_preferences.language).
_LANG_CODES: dict[str, str] = {
    "hindi": "hi",
    "hi": "hi",
    "hi-in": "hi",
    "english": "en",
    "en": "en",
    "en-in": "en",
}

# Piper voice names stored in user_preferences.tts_voice.
_TTS_BY_LANG: dict[str, str] = {
    "hi": "hi_IN-priyamvada-medium",
    "en": "en_IN-spicor-medium",
}


def normalize_language(language: str | None) -> str | None:
    if not language:
        return None
    return _LANG_CODES.get(language.strip().lower(), language[:16])


def tts_voice_for_language(language_code: str | None) -> str | None:
    if not language_code:
        return None
    return _TTS_BY_LANG.get(language_code)


def resolve_user_ref(user_ref: str | None, session_id: str | None = None) -> str:
    """Prefer explicit user_ref; fall back to session-scoped id for anonymous widgets."""
    if user_ref and user_ref.strip():
        return user_ref.strip()
    if session_id:
        return f"session:{session_id}"
    return "anonymous"


class TelemetryService:
    """Write analytics / preferences / audit rows without touching business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self._analytics = AnalyticsRepository(session)
        self._prefs = UserPreferenceRepository(session)
        self._audit = AuditLogRepository(session)

    async def record_chat_turn(
        self,
        *,
        session_id: str,
        message_id: str,
        user_ref: str | None,
        language: str | None,
        input_type: str,
        latency_ms: int,
        chunk_count: int,
        used_fallback: bool,
        client_ip: str | None = None,
    ) -> None:
        lang_code = normalize_language(language)
        event_type = "chat_fallback" if used_fallback else "chat_turn"
        resolved_ref = resolve_user_ref(user_ref, session_id)
        await self._analytics.add(
            AnalyticsEvent(
                session_id=session_id,
                event_type=event_type,
                payload={
                    "message_id": message_id,
                    "input_type": input_type,
                    "latency_ms": latency_ms,
                    "language": lang_code or language,
                    "chunk_count": chunk_count,
                    "used_fallback": used_fallback,
                    "user_ref": resolved_ref,
                },
            )
        )
        await self._prefs.upsert(
            resolved_ref,
            language=lang_code or "en",
            tts_voice=tts_voice_for_language(lang_code),
        )
        await self._audit.add(
            AuditLog(
                actor=resolved_ref,
                action="chat.message",
                entity="message",
                entity_id=message_id,
                ip=client_ip,
            )
        )

    async def upsert_user_preferences(
        self,
        *,
        user_ref: str,
        theme: str | None = None,
        language: str | None = None,
        voice_enabled: bool | None = None,
        tts_voice: str | None = None,
        client_ip: str | None = None,
    ) -> UserPreference:
        """Create or update widget preferences (theme, language, voice)."""
        ref = resolve_user_ref(user_ref)
        lang_code = normalize_language(language) if language else None
        fields: dict[str, object] = {}
        if theme:
            fields["theme"] = theme
        if lang_code:
            fields["language"] = lang_code
            fields["tts_voice"] = tts_voice or tts_voice_for_language(lang_code)
        elif tts_voice:
            fields["tts_voice"] = tts_voice
        if voice_enabled is not None:
            fields["voice_enabled"] = voice_enabled

        pref = await self._prefs.upsert(ref, **fields)

        await self._analytics.add(
            AnalyticsEvent(
                session_id=None,
                event_type="preference_updated",
                payload={
                    "user_ref": ref,
                    "theme": pref.theme,
                    "language": pref.language,
                    "voice_enabled": pref.voice_enabled,
                    "tts_voice": pref.tts_voice,
                },
            )
        )
        await self._audit.add(
            AuditLog(
                actor=ref,
                action="preference.update",
                entity="user_preference",
                entity_id=pref.id,
                ip=client_ip,
            )
        )
        return pref

    async def record_session_created(
        self,
        *,
        session_id: str,
        channel: str,
        user_ref: str | None,
        client_ip: str | None = None,
    ) -> None:
        await self._analytics.add(
            AnalyticsEvent(
                session_id=session_id,
                event_type="session_created",
                payload={"channel": channel, "user_ref": user_ref},
            )
        )
        await self._audit.add(
            AuditLog(
                actor=user_ref or "anonymous",
                action="session.create",
                entity="session",
                entity_id=session_id,
                ip=client_ip,
            )
        )

    async def record_session_cleared(
        self,
        *,
        session_id: str,
        user_ref: str | None = None,
        client_ip: str | None = None,
    ) -> None:
        await self._analytics.add(
            AnalyticsEvent(
                session_id=session_id,
                event_type="session_cleared",
                payload={"user_ref": user_ref},
            )
        )
        await self._audit.add(
            AuditLog(
                actor=user_ref or "anonymous",
                action="session.clear",
                entity="session",
                entity_id=session_id,
                ip=client_ip,
            )
        )

    async def record_feedback(
        self,
        *,
        feedback_id: str,
        message_id: str,
        rating: str,
        user_ref: str | None = None,
        client_ip: str | None = None,
    ) -> None:
        await self._analytics.add(
            AnalyticsEvent(
                session_id=None,
                event_type="feedback_submitted",
                payload={
                    "feedback_id": feedback_id,
                    "message_id": message_id,
                    "rating": rating,
                    "user_ref": user_ref,
                },
            )
        )
        await self._audit.add(
            AuditLog(
                actor=user_ref or "anonymous",
                action="feedback.submit",
                entity="feedback",
                entity_id=feedback_id,
                ip=client_ip,
            )
        )

    async def record_voice_transcript(
        self,
        *,
        session_id: str | None,
        text_length: int,
        stt_language: str | None,
        user_ref: str | None = None,
    ) -> None:
        await self._analytics.add(
            AnalyticsEvent(
                session_id=session_id,
                event_type="voice_transcribe",
                payload={
                    "text_length": text_length,
                    "stt_language": stt_language,
                    "user_ref": user_ref,
                },
            )
        )
