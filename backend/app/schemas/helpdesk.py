"""Helpdesk wizard request/response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FieldType = Literal["choice", "text", "phone", "email", "number", "date", "textarea"]


class HelpdeskOption(BaseModel):
    id: str
    label: str


class HelpdeskStepView(BaseModel):
    step_id: str
    message: str
    field_type: FieldType
    options: list[HelpdeskOption] = Field(default_factory=list)
    placeholder: str | None = None
    required: bool = True
    progress: int = Field(ge=0, le=100, description="0-100 completion hint for UI")


class HelpdeskStartResponse(BaseModel):
    session_id: str
    step: HelpdeskStepView


class HelpdeskRespondRequest(BaseModel):
    session_id: str
    answer: str


class HelpdeskRespondResponse(BaseModel):
    session_id: str
    completed: bool
    step: HelpdeskStepView | None = None
    summary: dict[str, Any] | None = None
    external_ref: str | None = None
    message: str | None = None
