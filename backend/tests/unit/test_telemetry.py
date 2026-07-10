"""Unit tests for telemetry persistence."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import AnalyticsEvent, AuditLog, Session, UserPreference
from app.db.repositories import SessionRepository
from app.services.telemetry_service import TelemetryService, normalize_language


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
async def test_record_chat_turn_fills_all_tables(db_session) -> None:
    sess = await SessionRepository(db_session).add(
        Session(channel="text", user_ref="visitor-42")
    )
    telemetry = TelemetryService(db_session)
    await telemetry.record_chat_turn(
        session_id=sess.id,
        message_id="msg-1",
        user_ref="visitor-42",
        language="Hindi",
        input_type="text",
        latency_ms=850,
        chunk_count=3,
        used_fallback=False,
        client_ip="127.0.0.1",
    )

    analytics = (await db_session.execute(select(AnalyticsEvent))).scalars().all()
    assert len(analytics) == 1
    assert analytics[0].event_type == "chat_turn"
    assert analytics[0].payload["language"] == "hi"
    assert analytics[0].payload["latency_ms"] == 850

    prefs = (await db_session.execute(select(UserPreference))).scalars().all()
    assert len(prefs) == 1
    assert prefs[0].user_ref == "visitor-42"
    assert prefs[0].language == "hi"
    assert prefs[0].tts_voice == "hi_IN-priyamvada-medium"

    audits = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(audits) == 1
    assert audits[0].action == "chat.message"
    assert audits[0].entity_id == "msg-1"
    assert audits[0].ip == "127.0.0.1"


def test_normalize_language() -> None:
    assert normalize_language("Hindi") == "hi"
    assert normalize_language("English") == "en"


@pytest.mark.asyncio
async def test_upsert_user_preferences_creates_row(db_session) -> None:
    telemetry = TelemetryService(db_session)
    pref = await telemetry.upsert_user_preferences(
        user_ref="widget-abc",
        theme="dark",
        language="English",
        voice_enabled=False,
        client_ip="10.0.0.1",
    )
    assert pref.user_ref == "widget-abc"
    assert pref.theme == "dark"
    assert pref.language == "en"
    assert pref.voice_enabled is False

    analytics = (await db_session.execute(select(AnalyticsEvent))).scalars().all()
    assert any(e.event_type == "preference_updated" for e in analytics)

    audits = (await db_session.execute(select(AuditLog))).scalars().all()
    assert any(a.action == "preference.update" for a in audits)


@pytest.mark.asyncio
async def test_record_chat_turn_without_user_ref_uses_session_fallback(db_session) -> None:
    sess = await SessionRepository(db_session).add(Session(channel="text"))
    telemetry = TelemetryService(db_session)
    await telemetry.record_chat_turn(
        session_id=sess.id,
        message_id="msg-2",
        user_ref=None,
        language="en",
        input_type="text",
        latency_ms=100,
        chunk_count=1,
        used_fallback=False,
    )
    prefs = (await db_session.execute(select(UserPreference))).scalars().all()
    assert len(prefs) == 1
    assert prefs[0].user_ref == f"session:{sess.id}"
