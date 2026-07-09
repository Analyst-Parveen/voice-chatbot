"""Suggested starter questions.

Static for now; Phase 6 can derive these from the ingested knowledge base or
the most frequent questions in analytics.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.suggestions import SuggestionsResponse

router = APIRouter(tags=["suggestions"])

_DEFAULT_SUGGESTIONS = [
    "What products do you offer?",
    "What are your business hours?",
    "How do I contact support?",
    "What is your return policy?",
]


@router.get("/suggestions", response_model=SuggestionsResponse, summary="Starter questions")
async def suggestions() -> SuggestionsResponse:
    return SuggestionsResponse(suggestions=_DEFAULT_SUGGESTIONS)
