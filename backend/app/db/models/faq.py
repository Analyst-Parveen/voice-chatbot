"""FAQ / intent models (voiceai.faq_*) — the pre-answered knowledge layer.

One row per INTENT; many question variants (any language/script) and one answer
per language point back to it. Retrieval matches a user query against the
question variants and serves the intent's stored answer directly — no LLM at
match time — for fast, consistent, curated replies.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, fk_target, utcnow
from app.db.types import GUID, new_uuid


class FAQIntent(Base, TimestampMixin):
    """A single answerable intent (e.g. ``claim_process``)."""

    __tablename__ = "faq_intents"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    intent_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    questions: Mapped[list["FAQQuestion"]] = relationship(
        back_populates="intent", cascade="all, delete-orphan", lazy="selectin"
    )
    answers: Mapped[list["FAQAnswer"]] = relationship(
        back_populates="intent", cascade="all, delete-orphan", lazy="selectin"
    )
    sources: Mapped[list["FAQSource"]] = relationship(
        back_populates="intent", cascade="all, delete-orphan", lazy="selectin"
    )


class FAQQuestion(Base, TimestampMixin):
    """One phrasing variant of an intent (any language/script)."""

    __tablename__ = "faq_questions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    intent_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey(fk_target("faq_intents.id"), ondelete="CASCADE"),
        nullable=False, index=True,
    )
    text: Mapped[str] = mapped_column(String(512), nullable=False)
    language_tag: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    is_quick_question: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    intent: Mapped["FAQIntent"] = relationship(back_populates="questions")


class FAQAnswer(Base, TimestampMixin):
    """The stored answer for an intent in one language ('en' | 'hi')."""

    __tablename__ = "faq_answers"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    intent_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey(fk_target("faq_intents.id"), ondelete="CASCADE"),
        nullable=False, index=True,
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)

    intent: Mapped["FAQIntent"] = relationship(back_populates="answers")


class FAQSource(Base, TimestampMixin):
    """Document that an intent's answer was generated from (provenance)."""

    __tablename__ = "faq_sources"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    intent_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey(fk_target("faq_intents.id"), ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source: Mapped[str] = mapped_column(String(512), nullable=False)

    intent: Mapped["FAQIntent"] = relationship(back_populates="sources")
