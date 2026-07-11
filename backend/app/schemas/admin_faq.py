"""Admin FAQ management schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FAQQuestionView(BaseModel):
    id: str
    text: str
    language_tag: str
    is_quick_question: bool


class FAQAnswerView(BaseModel):
    id: str
    language: str
    answer_text: str


class FAQIntentView(BaseModel):
    id: str
    intent_key: str
    category: str | None
    status: str
    enabled: bool
    questions: list[FAQQuestionView]
    answers: list[FAQAnswerView]
    sources: list[str]


class FAQIntentListResponse(BaseModel):
    intents: list[FAQIntentView]
    total: int


class FAQIntentUpdateRequest(BaseModel):
    enabled: bool | None = Field(default=None)
    category: str | None = Field(default=None)
    status: str | None = Field(default=None)


class FAQQuestionUpdateRequest(BaseModel):
    text: str | None = Field(default=None)
    is_quick_question: bool | None = Field(default=None)


class FAQAnswerUpdateRequest(BaseModel):
    answer_text: str = Field(...)


class ReindexResponse(BaseModel):
    indexed: int
