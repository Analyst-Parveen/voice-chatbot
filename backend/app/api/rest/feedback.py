"""Feedback endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import DbSession
from app.core.exceptions import NotFoundError
from app.db.models import Feedback
from app.db.repositories import FeedbackRepository, MessageRepository
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.telemetry_service import TelemetryService

router = APIRouter(tags=["feedback"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/feedback", response_model=FeedbackResponse, summary="Rate a message")
async def submit_feedback(
    payload: FeedbackRequest, db: DbSession, request: Request
) -> FeedbackResponse:
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
    await TelemetryService(db).record_feedback(
        feedback_id=created.id,
        message_id=payload.message_id,
        rating=payload.rating.value,
        client_ip=_client_ip(request),
    )
    return FeedbackResponse(id=created.id)
