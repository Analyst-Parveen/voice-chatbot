"""Async database engine, session factory, and helpers.

Builds the connection URL from settings so the same code targets the SQLite dev
fallback or the production MS SQL Server purely via ``.env``. The engine and
session factory are lazily created singletons; ``dispose_engine`` is called on
app shutdown (see ``main.py`` lifespan).

Migrations use a *sync* URL (see ``build_sync_url``) — that's the normal Alembic
pattern and avoids needing async drivers at migration time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _mssql_query(settings: Settings) -> str:
    """ODBC connection query string (driver + sensible defaults)."""
    driver = quote_plus(settings.mssql_driver)
    return f"driver={driver}&TrustServerCertificate=yes"


def build_async_url(settings: Settings) -> str:
    """Async SQLAlchemy URL for the runtime app."""
    if settings.use_sqlite:
        return f"sqlite+aiosqlite:///{settings.sqlite_path}"
    user = quote_plus(settings.mssql_user)
    pwd = quote_plus(settings.mssql_password)
    host, port, db = settings.mssql_host, settings.mssql_port, settings.mssql_db
    return f"mssql+aioodbc://{user}:{pwd}@{host}:{port}/{db}?{_mssql_query(settings)}"


def build_sync_url(settings: Settings) -> str:
    """Sync SQLAlchemy URL used by Alembic migrations."""
    if settings.use_sqlite:
        return f"sqlite:///{settings.sqlite_path}"
    user = quote_plus(settings.mssql_user)
    pwd = quote_plus(settings.mssql_password)
    host, port, db = settings.mssql_host, settings.mssql_port, settings.mssql_db
    return f"mssql+pyodbc://{user}:{pwd}@{host}:{port}/{db}?{_mssql_query(settings)}"


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _engine
    if _engine is None:
        url = build_async_url(get_settings())
        _engine = create_async_engine(url, pool_pre_ping=True, future=True)
        logger.info("Database engine created (%s)", url.split("://", 1)[0])
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, commit on success, rollback on error."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping_database() -> bool:
    """Return True if the database answers a trivial query."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - health probe must not raise
        logger.warning("Database ping failed: %s", exc)
        return False


async def dispose_engine() -> None:
    """Dispose the engine on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
