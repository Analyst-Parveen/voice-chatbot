"""Audit log model (voiceai.audit_logs) — security/audit trail."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.types import GUID, new_uuid


class AuditLog(Base, TimestampMixin):
    """An audited action (who did what to which entity, from where)."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
