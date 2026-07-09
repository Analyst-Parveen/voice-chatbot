"""Unit tests for the anti-hallucination ValidationService."""

from __future__ import annotations

from app.core.config import Settings
from app.services.dto import RetrievedChunk
from app.services.validation_service import FALLBACK_MESSAGE, ValidationService


def _settings(**kw) -> Settings:
    base = {"DB_BACKEND": "sqlite"}
    base.update(kw)
    return Settings(**base)


def _chunk(score: float, text: str = "some grounding context here") -> RetrievedChunk:
    return RetrievedChunk(chunk_id="c", source="s", score=score, text=text)


def test_rag_disabled_always_answers() -> None:
    v = ValidationService(_settings(RAG_ENABLED=False))
    assert v.should_answer([]) is True
    assert v.finalize_answer("hello", []) == "hello"


def test_rag_enabled_no_chunks_falls_back() -> None:
    v = ValidationService(_settings(RAG_ENABLED=True))
    assert v.should_answer([]) is False
    assert v.finalize_answer("hello", []) == FALLBACK_MESSAGE


def test_rag_enabled_low_score_falls_back() -> None:
    v = ValidationService(_settings(RAG_ENABLED=True, RAG_SCORE_THRESHOLD=0.5))
    assert v.should_answer([_chunk(0.2)]) is False


def test_rag_enabled_strong_chunk_answers() -> None:
    v = ValidationService(
        _settings(RAG_ENABLED=True, RAG_SCORE_THRESHOLD=0.5, RAG_MIN_CONTEXT_CHARS=5)
    )
    chunks = [_chunk(0.8)]
    assert v.should_answer(chunks) is True
    assert v.finalize_answer("grounded answer", chunks) == "grounded answer"


def test_min_context_chars_enforced() -> None:
    v = ValidationService(
        _settings(RAG_ENABLED=True, RAG_SCORE_THRESHOLD=0.1, RAG_MIN_CONTEXT_CHARS=100)
    )
    assert v.should_answer([_chunk(0.9, text="short")]) is False


def test_is_grounded() -> None:
    v = ValidationService(_settings(RAG_ENABLED=True, RAG_SCORE_THRESHOLD=0.4))
    assert v.is_grounded(_chunk(0.5)) is True
    assert v.is_grounded(_chunk(0.3)) is False
