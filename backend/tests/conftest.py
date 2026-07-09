"""Shared test fixtures.

Points the application's database engine at an isolated temporary SQLite file
and creates all tables, so both dependency-injected endpoints (REST) and the
globally-accessed sessionmaker (WebSockets) use the same throwaway database.

Two deliberate choices avoid cross-event-loop aiosqlite deadlocks under
Starlette's TestClient (which runs WebSocket handlers in their own loop):
- the schema is created with a *sync* engine (no asyncio loop involved), and
- the async test engine uses ``NullPool`` so every connection is opened fresh
  in whatever loop is currently running (never reused across loops).
"""

from __future__ import annotations

import os

# Pin the test configuration BEFORE any app import (app.db.base reads settings at
# import time). Env vars take precedence over the developer's .env, so the suite
# runs identically regardless of whether .env is stub / local-light / docker.
os.environ["RUN_MODE"] = "stub"
os.environ["RAG_ENABLED"] = "false"
os.environ["DB_BACKEND"] = "sqlite"

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.db.models  # noqa: F401,E402 - register all models on Base.metadata
import app.db.session as db_session  # noqa: E402
from app.db.base import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _isolated_test_db(tmp_path_factory: pytest.TempPathFactory):
    db_path: Path = tmp_path_factory.mktemp("db") / "test.sqlite3"

    # Create the schema with a plain sync engine — no event loop involved.
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    # Async engine for the app; NullPool avoids cross-loop connection reuse.
    async_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool
    )
    db_session._engine = async_engine
    db_session._sessionmaker = async_sessionmaker(async_engine, expire_on_commit=False)

    yield
