"""Unit tests for prompt building and text cleaning."""

from __future__ import annotations

from app.rag.prompt_builder import build_system_prompt, format_context
from app.services.dto import RetrievedChunk
from app.services.validation_service import FALLBACK_MESSAGE
from ingestion.cleaning import clean_text


def test_system_prompt_enforces_fallback() -> None:
    prompt = build_system_prompt()
    assert FALLBACK_MESSAGE in prompt
    assert "ONLY" in prompt
    assert "same language" in prompt


def test_format_context_empty() -> None:
    assert format_context([]) == ""


def test_format_context_labels_sources() -> None:
    chunks = [
        RetrievedChunk(chunk_id="1", source="faq.md", score=0.9, text="Return within 30 days."),
        RetrievedChunk(chunk_id="2", source="policy.pdf", score=0.8, text="Free shipping over $50."),
    ]
    ctx = format_context(chunks)
    assert ctx.startswith("CONTEXT:")
    assert "faq.md" in ctx and "policy.pdf" in ctx
    assert "Return within 30 days." in ctx


def test_clean_text_normalizes_whitespace() -> None:
    dirty = "Hello   world\r\n\n\n\nGoodbye\x00\x07 world  \n"
    cleaned = clean_text(dirty)
    assert "\x00" not in cleaned and "\x07" not in cleaned
    assert "Hello world" in cleaned
    assert "\n\n\n" not in cleaned  # blank lines collapsed
    assert not cleaned.endswith(" ")
