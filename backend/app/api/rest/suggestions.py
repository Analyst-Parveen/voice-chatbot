"""Suggested starter questions.

Static for now; Phase 6 can derive these from the ingested knowledge base or
the most frequent questions in analytics.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.suggestions import SuggestionsResponse
from app.services.starter_faqs import get_starter_questions

router = APIRouter(tags=["suggestions"])


@router.get("/suggestions", response_model=SuggestionsResponse, summary="Starter questions")
async def suggestions(
    language: str | None = Query(
        default=None,
        description="Reply language (e.g. English, Hindi) for localized labels.",
    ),
) -> SuggestionsResponse:
    return SuggestionsResponse(suggestions=get_starter_questions(language))
