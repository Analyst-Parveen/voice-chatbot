"""Repository tests against an isolated in-memory SQLite database.

Uses ``Base.metadata.create_all`` (schema is None on SQLite) so no migration or
external server is needed — runs anywhere, including a low-config PC.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Feedback, Message, Retrieval, Session, UserPreference
from app.db.repositories import (
    FeedbackRepository,
    MessageRepository,
    RetrievalRepository,
    SessionRepository,
    UserPreferenceRepository,
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_crud_and_uuid_pk(db_session) -> None:
    repo = SessionRepository(db_session)
    created = await repo.add(Session(channel="text", user_ref="user-1"))
    assert created.id  # GUID default generated
    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.channel == "text"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_messages_persist_and_order(db_session) -> None:
    session = await SessionRepository(db_session).add(Session(channel="text"))
    msg_repo = MessageRepository(db_session)
    await msg_repo.add(Message(session_id=session.id, role="user",
                               content="hello", input_type="text"))
    await msg_repo.add(Message(session_id=session.id, role="assistant",
                               content="hi there", input_type="text"))

    history = await msg_repo.list_by_session(session.id)
    assert [m.role for m in history] == ["user", "assistant"]
    assert history[0].content == "hello"


@pytest.mark.asyncio
async def test_retrieval_and_feedback_fk(db_session) -> None:
    session = await SessionRepository(db_session).add(Session(channel="voice"))
    msg = await MessageRepository(db_session).add(
        Message(session_id=session.id, role="assistant", content="answer", input_type="voice")
    )
    await RetrievalRepository(db_session).add(
        Retrieval(message_id=msg.id, chunk_id="c1", source="faq.md", score=0.9, used=True)
    )
    await FeedbackRepository(db_session).add(
        Feedback(message_id=msg.id, rating="up", comment="great")
    )

    retrievals = await RetrievalRepository(db_session).list_by_message(msg.id)
    assert len(retrievals) == 1
    assert retrievals[0].score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_user_preferences_lookup(db_session) -> None:
    repo = UserPreferenceRepository(db_session)
    await repo.add(UserPreference(user_ref="user-9", theme="dark", language="en"))
    found = await repo.get_by_user("user-9")
    assert found is not None
    assert found.theme == "dark"
    assert await repo.get_by_user("nobody") is None
