"""Conversation history endpoint (paginated)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.history import HistoryResponse, MessageOut
from app.services.memory_service import MemoryService

router = APIRouter(tags=["history"])


@router.get(
    "/history/{session_id}",
    response_model=HistoryResponse,
    summary="Get a session's messages (paginated)",
)
async def get_history(
    session_id: str,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> HistoryResponse:
    memory = MemoryService(db)
    messages = await memory.get_history(session_id, limit=limit, offset=offset)
    total = await memory.count_messages(session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[MessageOut.model_validate(m) for m in messages],
        total=total,
        limit=limit,
        offset=offset,
    )
