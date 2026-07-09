"""Suggested starter questions schema."""

from __future__ import annotations

from pydantic import BaseModel


class SuggestionsResponse(BaseModel):
    suggestions: list[str]
