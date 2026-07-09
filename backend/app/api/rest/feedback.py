"""Feedback endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.core.exceptions import NotFoundError
from app.db.models import Feedback
from app.db.repositories import FeedbackRepository, MessageRepository
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse, summary="Rate a message")
async def submit_feedback(payload: FeedbackRequest, db: DbSession) -> FeedbackResponse:
    # Ensure the target message exists before recording feedback.
    if await MessageRepository(db).get(payload.message_id) is None:
        raise NotFoundError("Message not found", details={"message_id": payload.message_id})

    created = await FeedbackRepository(db).add(
        Feedback(
            message_id=payload.message_id,
            rating=payload.rating.value,
            comment=payload.comment,
        )
    )
    return FeedbackResponse(id=created.id)
