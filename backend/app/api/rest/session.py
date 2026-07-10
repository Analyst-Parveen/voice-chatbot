"""Session lifecycle endpoints (create / clear conversation)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AuthDep, DbSession
from app.core.exceptions import NotFoundError
from app.schemas.session import SessionCreateRequest, SessionResponse
from app.services.memory_service import MemoryService
from app.services.telemetry_service import TelemetryService

router = APIRouter(tags=["session"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new conversation session",
)
async def create_session(
    payload: SessionCreateRequest,
    db: DbSession,
    auth: AuthDep,
    request: Request,
) -> SessionResponse:
    memory = MemoryService(db)
    user_ref = payload.user_ref or auth.user_ref
    session = await memory.get_or_create_session(
        None, channel=payload.channel.value, user_ref=user_ref
    )
    await TelemetryService(db).record_session_created(
        session_id=session.id,
        channel=session.channel,
        user_ref=user_ref,
        client_ip=_client_ip(request),
    )
    return SessionResponse(
        session_id=session.id, channel=session.channel, created_at=session.created_at
    )


@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear a conversation (delete session and its messages)",
)
async def clear_session(session_id: str, db: DbSession, request: Request) -> Response:
    memory = MemoryService(db)
    deleted = await memory.clear_session(session_id)
    if deleted is None:
        raise NotFoundError("Session not found", details={"session_id": session_id})
    await TelemetryService(db).record_session_cleared(
        session_id=session_id,
        user_ref=deleted.user_ref,
        client_ip=_client_ip(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
