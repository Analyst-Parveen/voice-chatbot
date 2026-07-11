"""faq intent tables (voiceai.faq_*)

Adds the curated FAQ/intent layer: one row per intent, with question variants,
per-language answers, and provenance sources. Written by hand so it renders on
both dialects (GUID -> UNIQUEIDENTIFIER / CHAR(36)) and honors the active schema.

Revision ID: 0002_faq
Revises: 0001_initial
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.base import SCHEMA
from app.db.types import GUID

# revision identifiers, used by Alembic.
revision: str = "0002_faq"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fk(target: str) -> str:
    return f"{SCHEMA}.{target}" if SCHEMA else target


def upgrade() -> None:
    op.create_table(
        "faq_intents",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("intent_key", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_faq_intents"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_faq_intents_intent_key", "faq_intents", ["intent_key"],
        unique=True, schema=SCHEMA,
    )

    op.create_table(
        "faq_questions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("intent_id", GUID(), nullable=False),
        sa.Column("text", sa.String(length=512), nullable=False),
        sa.Column("language_tag", sa.String(length=16), nullable=False),
        sa.Column("is_quick_question", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_faq_questions"),
        sa.ForeignKeyConstraint(
            ["intent_id"], [_fk("faq_intents.id")],
            name="fk_faq_questions_intent_id", ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_faq_questions_intent_id", "faq_questions", ["intent_id"], schema=SCHEMA
    )

    op.create_table(
        "faq_answers",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("intent_id", GUID(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_faq_answers"),
        sa.ForeignKeyConstraint(
            ["intent_id"], [_fk("faq_intents.id")],
            name="fk_faq_answers_intent_id", ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_faq_answers_intent_id", "faq_answers", ["intent_id"], schema=SCHEMA
    )

    op.create_table(
        "faq_sources",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("intent_id", GUID(), nullable=False),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_faq_sources"),
        sa.ForeignKeyConstraint(
            ["intent_id"], [_fk("faq_intents.id")],
            name="fk_faq_sources_intent_id", ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_faq_sources_intent_id", "faq_sources", ["intent_id"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_table("faq_sources", schema=SCHEMA)
    op.drop_table("faq_answers", schema=SCHEMA)
    op.drop_table("faq_questions", schema=SCHEMA)
    op.drop_table("faq_intents", schema=SCHEMA)
