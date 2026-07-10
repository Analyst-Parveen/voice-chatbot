"""Unit tests for English → Hindi translation layer."""

from __future__ import annotations

import pytest

from app.services.dto import LLMRequest
from app.services.hindi_translator import (
    is_hindi_mode,
    should_translate_to_hindi,
    translate_to_hindi,
)


class _FakeLLM:
    async def complete(self, request: LLMRequest) -> str:
        return "हमारी टीम आपकी मदद करेगी।"

    async def stream(self, request: LLMRequest):
        yield ""


@pytest.mark.asyncio
async def test_translate_to_hindi_returns_devanagari() -> None:
    out = await translate_to_hindi(
        "Our team will help you.",
        _FakeLLM(),
        user_question="aap kya kr rhe ho",
    )
    assert "मदद" in out


def test_is_hindi_mode() -> None:
    assert is_hindi_mode("Hindi")
    assert not is_hindi_mode("English")


def test_should_translate_skips_devanagari() -> None:
    assert not should_translate_to_hindi("Hindi", "हमारी टीम")
    assert should_translate_to_hindi("Hindi", "Our team will help.")
