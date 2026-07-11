"""Admin FAQ management endpoints (/api/admin/faq/*).

Review and curate generated FAQs: approve, edit, enable/disable, flag quick
questions, and reindex vectors. Protected by the existing auth dependency
(JWT when AUTH_ENABLED; anonymous allowed in local dev, same policy as the
rest of the API).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AuthDep, DbSession, SettingsDep
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import FAQAnswer, FAQIntent, FAQQuestion
from app.db.repositories import FAQIntentRepository
from app.schemas.admin_faq import (
    FAQAnswerUpdateRequest,
    FAQAnswerView,
    FAQIntentListResponse,
    FAQIntentUpdateRequest,
    FAQIntentView,
    FAQQuestionUpdateRequest,
    FAQQuestionView,
    ReindexResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/faq", tags=["admin-faq"])


def _view(intent: FAQIntent) -> FAQIntentView:
    return FAQIntentView(
        id=intent.id,
        intent_key=intent.intent_key,
        category=intent.category,
        status=intent.status,
        enabled=intent.enabled,
        questions=[
            FAQQuestionView(
                id=q.id,
                text=q.text,
                language_tag=q.language_tag,
                is_quick_question=q.is_quick_question,
            )
            for q in intent.questions
        ],
        answers=[
            FAQAnswerView(id=a.id, language=a.language, answer_text=a.answer_text)
            for a in intent.answers
        ],
        sources=[s.source for s in intent.sources],
    )


@router.get("/intents", response_model=FAQIntentListResponse, summary="List FAQ intents")
async def list_intents(
    db: DbSession,
    auth: AuthDep,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> FAQIntentListResponse:
    intents = await FAQIntentRepository(db).list_all(
        status=status, limit=limit, offset=offset
    )
    return FAQIntentListResponse(
        intents=[_view(i) for i in intents], total=len(intents)
    )


@router.post(
    "/intents/{intent_id}/approve",
    response_model=FAQIntentView,
    summary="Approve an intent (makes it matchable)",
)
async def approve_intent(intent_id: str, db: DbSession, auth: AuthDep) -> FAQIntentView:
    intent = await FAQIntentRepository(db).get(intent_id)
    if intent is None:
        raise NotFoundError("Intent not found", details={"intent_id": intent_id})
    intent.status = "approved"
    await db.flush()
    return _view(intent)


@router.patch(
    "/intents/{intent_id}",
    response_model=FAQIntentView,
    summary="Edit an intent (enable/disable, category, status)",
)
async def update_intent(
    intent_id: str, payload: FAQIntentUpdateRequest, db: DbSession, auth: AuthDep
) -> FAQIntentView:
    intent = await FAQIntentRepository(db).get(intent_id)
    if intent is None:
        raise NotFoundError("Intent not found", details={"intent_id": intent_id})
    if payload.enabled is not None:
        intent.enabled = payload.enabled
    if payload.category is not None:
        intent.category = payload.category
    if payload.status is not None:
        intent.status = payload.status
    await db.flush()
    return _view(intent)


@router.patch(
    "/questions/{question_id}",
    response_model=FAQQuestionView,
    summary="Edit a question / flag as quick question",
)
async def update_question(
    question_id: str, payload: FAQQuestionUpdateRequest, db: DbSession, auth: AuthDep
) -> FAQQuestionView:
    question = await db.get(FAQQuestion, question_id)
    if question is None:
        raise NotFoundError("Question not found", details={"question_id": question_id})
    if payload.text is not None:
        question.text = payload.text
    if payload.is_quick_question is not None:
        question.is_quick_question = payload.is_quick_question
    await db.flush()
    return FAQQuestionView(
        id=question.id,
        text=question.text,
        language_tag=question.language_tag,
        is_quick_question=question.is_quick_question,
    )


@router.patch(
    "/answers/{answer_id}",
    response_model=FAQAnswerView,
    summary="Edit a stored answer",
)
async def update_answer(
    answer_id: str, payload: FAQAnswerUpdateRequest, db: DbSession, auth: AuthDep
) -> FAQAnswerView:
    answer = await db.get(FAQAnswer, answer_id)
    if answer is None:
        raise NotFoundError("Answer not found", details={"answer_id": answer_id})
    answer.answer_text = payload.answer_text
    await db.flush()
    return FAQAnswerView(
        id=answer.id, language=answer.language, answer_text=answer.answer_text
    )


@router.post(
    "/reindex",
    response_model=ReindexResponse,
    summary="Rebuild FAQ vectors from the database",
)
async def reindex(db: DbSession, auth: AuthDep, settings: SettingsDep) -> ReindexResponse:
    from ingestion.generate_faqs import _reindex

    indexed = await _reindex(db, settings)
    return ReindexResponse(indexed=indexed)
