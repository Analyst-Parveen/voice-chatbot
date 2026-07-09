"""Alembic migration environment.

Pulls the database URL from application settings (so it honors ``.env`` and the
SQLite/MS SQL split), and points autogenerate at the app's metadata. Runs in
sync mode using ``build_sync_url`` — the standard Alembic approach.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Import models so every table is registered on Base.metadata.
import app.db.models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import build_sync_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return build_sync_url(get_settings())


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_url(), poolclass=pool.NullPool, future=True)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
