"""Chat endpoint (non-streaming text turn)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AuthDep, ConversationManagerDep
from app.schemas.chat import ChatRequest, ChatResponse, Source

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse, summary="Send a text message")
async def chat(
    payload: ChatRequest,
    manager: ConversationManagerDep,
    auth: AuthDep,
) -> ChatResponse:
    """Run one conversation turn and return the grounded answer."""
    result = await manager.handle(
        session_id=payload.session_id,
        message=payload.message,
        input_type=payload.input_type.value,
        user_ref=auth.user_ref,
        language=payload.language,
    )
    return ChatResponse(
        session_id=result.session_id,
        message_id=result.message_id,
        answer=result.answer,
        latency_ms=result.latency_ms,
        sources=[
            Source(chunk_id=c.chunk_id, source=c.source, score=c.score)
            for c in result.sources
        ],
    )
