"""Declarative base, schema resolution, and common mixins.

All ORM models live under the ``voiceai`` schema on SQL Server so they never
collide with existing company tables. SQLite has no real schema support, so on
the dev fallback the schema is ``None`` (schema-less) — the same models work in
both places.

A constraint naming convention is applied so Alembic generates stable,
predictable index/FK/PK names across dialects.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

_settings = get_settings()

# Schema is applied on SQL Server only; None (schema-less) on the SQLite dev DB.
SCHEMA: str | None = None if _settings.use_sqlite else _settings.db_schema

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


def fk_target(table_and_column: str) -> str:
    """Schema-qualify a foreign key target (e.g. ``sessions.id``)."""
    return f"{SCHEMA}.{table_and_column}" if SCHEMA else table_and_column


def utcnow() -> datetime:
    """Timezone-aware current UTC time (used as a Python-side default)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base with schema + naming convention applied."""

    metadata = MetaData(schema=SCHEMA, naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds a ``created_at`` column defaulting to now (UTC)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
