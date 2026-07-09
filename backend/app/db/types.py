"""Cross-dialect column types.

``GUID`` renders as native ``UNIQUEIDENTIFIER`` on Microsoft SQL Server (the
production database) and as ``CHAR(36)`` everywhere else (the SQLite dev
fallback), while the Python side always works with plain string UUIDs. This is
what lets one set of models target both databases with no code changes.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID stored and returned as a string."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mssql":
            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return str(value)


def new_uuid() -> str:
    """Generate a new random UUID as a string (default for GUID PKs)."""
    return str(uuid.uuid4())
