"""Conversation memory — persists sessions and messages to SQL.

Wraps the repositories so the ConversationManager never touches the ORM. Bound
to a single request's ``AsyncSession``; the transaction is committed by the
caller (the ``get_db`` dependency for REST, or an explicit commit for WS).
"""

from __future__ import annotations

from app.db.models import Message, Retrieval, Session
from app.db.models.enums import Channel, Role
from app.db.repositories import (
    MessageRepository,
    RetrievalRepository,
    SessionRepository,
)
from app.services.dto import ChatMessage, RetrievedChunk


class MemoryService:
    def __init__(self, session) -> None:
        self._db = session
        self._sessions = SessionRepository(session)
        self._messages = MessageRepository(session)
        self._retrievals = RetrievalRepository(session)

    async def get_or_create_session(
        self,
        session_id: str | None,
        *,
        channel: str = Channel.TEXT.value,
        user_ref: str | None = None,
    ) -> Session:
        if session_id:
            existing = await self._sessions.get(session_id)
            if existing is not None:
                return existing
        return await self._sessions.add(Session(channel=channel, user_ref=user_ref))

    async def add_user_message(
        self, session_id: str, content: str, input_type: str
    ) -> Message:
        return await self._messages.add(
            Message(session_id=session_id, role=Role.USER.value,
                    content=content, input_type=input_type)
        )

    async def add_assistant_message(
        self, session_id: str, content: str, input_type: str, latency_ms: int
    ) -> Message:
        return await self._messages.add(
            Message(session_id=session_id, role=Role.ASSISTANT.value,
                    content=content, input_type=input_type, latency_ms=latency_ms)
        )

    async def recent_context(self, session_id: str, *, limit: int = 10) -> list[ChatMessage]:
        """Recent turns (chronological) mapped to LLM-friendly DTOs."""
        messages = await self._messages.recent_history(session_id, limit=limit)
        return [ChatMessage(role=m.role, content=m.content) for m in messages]

    async def get_history(
        self, session_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[Message]:
        return await self._messages.list_by_session(session_id, limit=limit, offset=offset)

    async def count_messages(self, session_id: str) -> int:
        return await self._messages.count_by_session(session_id)

    async def add_retrievals(
        self,
        message_id: str,
        chunks: list[RetrievedChunk],
        grounded_ids: set[str] | None = None,
    ) -> None:
        """Persist the retrieval audit trail for an assistant message.

        ``grounded_ids`` marks which chunks cleared the score threshold and thus
        actually grounded the answer (``used=True``); others are logged as
        considered-but-not-used for RAG debugging.
        """
        for chunk in chunks:
            used = True if grounded_ids is None else chunk.chunk_id in grounded_ids
            await self._retrievals.add(
                Retrieval(
                    message_id=message_id,
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    score=chunk.score,
                    used=used,
                )
            )

    async def touch(self, session_id: str) -> None:
        await self._sessions.touch(session_id)

    async def clear_session(self, session_id: str) -> Session | None:
        """Delete the session and (via cascade) all its messages. Returns it if found."""
        existing = await self._sessions.get(session_id)
        if existing is None:
            return None
        await self._sessions.delete(existing)
        return existing
