"""Session lifecycle endpoints (create / clear conversation)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import AuthDep, DbSession
from app.core.exceptions import NotFoundError
from app.schemas.session import SessionCreateRequest, SessionResponse
from app.services.memory_service import MemoryService

router = APIRouter(tags=["session"])


@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new conversation session",
)
async def create_session(
    payload: SessionCreateRequest, db: DbSession, auth: AuthDep
) -> SessionResponse:
    memory = MemoryService(db)
    session = await memory.get_or_create_session(
        None, channel=payload.channel.value, user_ref=payload.user_ref or auth.user_ref
    )
    return SessionResponse(
        session_id=session.id, channel=session.channel, created_at=session.created_at
    )


@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear a conversation (delete session and its messages)",
)
async def clear_session(session_id: str, db: DbSession) -> Response:
    cleared = await MemoryService(db).clear_session(session_id)
    if not cleared:
        raise NotFoundError("Session not found", details={"session_id": session_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
