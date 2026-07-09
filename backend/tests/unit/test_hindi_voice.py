"""Unit tests for Hindi TTS prep and prompt building."""

from __future__ import annotations

from app.rag.prompt_builder import build_system_prompt, detect_script_hint, wrap_user_message
from app.services.hindi_speech_prep import (
    classify_tts_script,
    is_roman_hindi,
    prepare_for_hindi_tts,
)
from app.services.validation_service import FALLBACK_MESSAGE, HINDI_FALLBACK_MESSAGE


def test_hindi_prompt_requires_hindi_only() -> None:
    prompt = build_system_prompt("Hindi")
    assert "Hindi" in prompt
    assert HINDI_FALLBACK_MESSAGE in prompt


def test_hinglish_script_hint() -> None:
    hint = detect_script_hint("aap kaise ho", "Hindi")
    assert hint is not None
    assert "Roman" in hint


def test_devanagari_script_hint() -> None:
    hint = detect_script_hint("आप कैसे हैं", "Hindi")
    assert hint is not None
    assert "Devanagari" in hint


def test_english_query_with_hindi_selected() -> None:
    hint = detect_script_hint("who are you", "Hindi")
    assert hint is not None
    assert "reply in Hindi" in hint


def test_wrap_user_message_hindi() -> None:
    wrapped = wrap_user_message("hello", "Hindi")
    assert "Hindi only" in wrapped
    assert "hello" in wrapped


def test_english_not_classified_as_hinglish() -> None:
    assert classify_tts_script("I am an artificial intelligence designed by Alibaba Cloud") == "english"


def test_roman_hindi_transliteration_for_tts() -> None:
    if not is_roman_hindi("namaste"):
        return
    out = prepare_for_hindi_tts("namaste")
    assert out != ""  # noqa: S101


def test_english_not_transliterated_for_tts() -> None:
    text = "I am an artificial intelligence designed by Alibaba Cloud"
    assert prepare_for_hindi_tts(text) == text
