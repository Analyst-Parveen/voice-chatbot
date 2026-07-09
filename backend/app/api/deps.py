"""Dependency injection providers.

Central place for FastAPI ``Depends`` factories. Endpoints declare typed
dependencies (``SettingsDep``, ``AuthDep``) instead of importing globals, which
keeps handlers testable and makes it trivial to swap implementations. Phase 4
adds service providers here (STT/TTS/LLM/RAG, chosen by run mode).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import AuthContext, resolve_auth
from app.db.session import get_db
from app.services.conversation_manager import ConversationManager
from app.services.factory import build_conversation_manager

# Settings (cached singleton).
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Async database session (commit on success, rollback on error).
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_auth_context(
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    """Resolve the caller's auth context (anonymous unless AUTH_ENABLED)."""
    return resolve_auth(authorization, settings)


# Auth context for the current request.
AuthDep = Annotated[AuthContext, Depends(get_auth_context)]


async def get_conversation_manager(
    db: DbSession, settings: SettingsDep
) -> ConversationManager:
    """Per-request ConversationManager (holds this request's DB session)."""
    return build_conversation_manager(db, settings)


# ConversationManager for the current request.
ConversationManagerDep = Annotated[
    ConversationManager, Depends(get_conversation_manager)
]
