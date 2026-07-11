"""Concrete repositories, one per entity.

Each extends :class:`BaseRepository` and adds query methods the service layer
(Phase 4+) needs. Kept intentionally small; grow as endpoints require.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update

from app.db.base import utcnow
from app.db.models import (
    AnalyticsEvent,
    AuditLog,
    FAQAnswer,
    FAQIntent,
    Feedback,
    Message,
    Retrieval,
    Session,
    UserPreference,
)
from app.db.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    model = Session

    async def touch(self, session_id: str) -> None:
        """Bump ``last_active_at`` for a session."""
        await self.session.execute(
            update(Session).where(Session.id == session_id).values(last_active_at=utcnow())
        )

    async def list_for_user(self, user_ref: str, *, limit: int = 50) -> list[Session]:
        result = await self.session.execute(
            select(Session)
            .where(Session.user_ref == user_ref)
            .order_by(Session.last_active_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_by_session(
        self, session_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_session(self, session_id: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Message).where(Message.session_id == session_id)
        )
        return int(result.scalar_one())

    async def recent_history(self, session_id: str, *, limit: int = 10) -> list[Message]:
        """Most recent messages (chronological) for building LLM context."""
        result = await self.session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))


class RetrievalRepository(BaseRepository[Retrieval]):
    model = Retrieval

    async def list_by_message(self, message_id: str) -> list[Retrieval]:
        result = await self.session.execute(
            select(Retrieval).where(Retrieval.message_id == message_id)
        )
        return list(result.scalars().all())


class FeedbackRepository(BaseRepository[Feedback]):
    model = Feedback


class AnalyticsRepository(BaseRepository[AnalyticsEvent]):
    model = AnalyticsEvent

    async def since(self, moment: datetime, *, limit: int = 1000) -> list[AnalyticsEvent]:
        result = await self.session.execute(
            select(AnalyticsEvent)
            .where(AnalyticsEvent.created_at >= moment)
            .order_by(AnalyticsEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class UserPreferenceRepository(BaseRepository[UserPreference]):
    model = UserPreference

    async def get_by_user(self, user_ref: str) -> UserPreference | None:
        result = await self.session.execute(
            select(UserPreference).where(UserPreference.user_ref == user_ref)
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_ref: str, **fields: object) -> UserPreference:
        """Create or update preferences for a user (one row per user_ref)."""
        existing = await self.get_by_user(user_ref)
        if existing is not None:
            for key, value in fields.items():
                if value is not None and hasattr(existing, key):
                    setattr(existing, key, value)
            existing.updated_at = utcnow()
            await self.session.flush()
            return existing
        pref = UserPreference(user_ref=user_ref, **fields)  # type: ignore[arg-type]
        return await self.add(pref)


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog


class FAQIntentRepository(BaseRepository[FAQIntent]):
    model = FAQIntent

    async def get_by_key(self, intent_key: str) -> FAQIntent | None:
        result = await self.session.execute(
            select(FAQIntent).where(FAQIntent.intent_key == intent_key)
        )
        return result.scalar_one_or_none()

    async def get_matchable(self, intent_key: str) -> FAQIntent | None:
        """An intent is matchable only when enabled and approved."""
        result = await self.session.execute(
            select(FAQIntent).where(
                FAQIntent.intent_key == intent_key,
                FAQIntent.enabled.is_(True),
                FAQIntent.status == "approved",
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, *, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[FAQIntent]:
        stmt = select(FAQIntent)
        if status:
            stmt = stmt.where(FAQIntent.status == status)
        stmt = stmt.order_by(FAQIntent.updated_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class FAQAnswerRepository(BaseRepository[FAQAnswer]):
    model = FAQAnswer

    async def get_for_intent(self, intent_id: str, language: str) -> FAQAnswer | None:
        result = await self.session.execute(
            select(FAQAnswer).where(
                FAQAnswer.intent_id == intent_id,
                FAQAnswer.language == language,
            )
        )
        return result.scalar_one_or_none()
