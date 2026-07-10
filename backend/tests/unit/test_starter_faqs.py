"""Starter FAQ lookup and localized suggestion labels."""

from __future__ import annotations

from app.services.starter_faqs import (
    get_starter_questions,
    lookup_starter_answer,
)


def test_starter_questions_english_default() -> None:
    questions = get_starter_questions(None)
    assert questions[0] == "What products do you offer?"
    assert len(questions) == 4


def test_starter_questions_hindi() -> None:
    questions = get_starter_questions("Hindi")
    assert any("\u0900" <= ch <= "\u097f" for ch in questions[0])
    assert len(questions) == 4


def test_lookup_english_question_english_answer() -> None:
    answer = lookup_starter_answer("What are your business hours?", "English")
    assert answer is not None
    assert "Monday to Friday" in answer
    assert "सोमवार" not in answer


def test_lookup_hindi_question_hindi_answer() -> None:
    answer = lookup_starter_answer(
        "आपके व्यापारिक घंटे क्या हैं?",
        "Hindi",
    )
    assert answer is not None
    assert "सोमवार" in answer


def test_lookup_unknown_returns_none() -> None:
    assert lookup_starter_answer("random question", "English") is None
