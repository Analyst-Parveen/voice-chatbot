"""English → fluent Devanagari Hindi for Hindi-mode replies.

Small local LLMs answer more reliably in English from RAG context. When the user
selects Hindi (including Roman Hinglish input), we generate in English then
translate once for display and TTS — same string for both (golden rule).
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.services.dto import LLMRequest
from app.services.hindi_speech_prep import is_devanagari
from app.services.interfaces import LLMService
from app.services.validation_service import FALLBACK_MESSAGE

logger = get_logger(__name__)

_TRANSLATE_SYSTEM = (
    "You are a fluent Hindi customer-care voice agent for an Indian company. "
    "Translate the given English answer into natural, clear Hindi using ONLY "
    "Devanagari script. Use polite spoken Hindi (जी, आप, कृपया) like a "
    "professional Hindi speaker on a helpdesk call. Keep company names, "
    "product names, URLs, and numbers unchanged. Do not add or remove facts. "
    "Output ONLY the Hindi translation — no English, no preamble."
)


def is_hindi_mode(language: str | None) -> bool:
    return (language or "").strip().lower() == "hindi"


def should_translate_to_hindi(language: str | None, text: str) -> bool:
    if not is_hindi_mode(language) or not text.strip():
        return False
    if text.strip() == FALLBACK_MESSAGE:
        return False
    return not is_devanagari(text)


async def translate_to_hindi(
    english_answer: str,
    llm: LLMService,
    *,
    user_question: str | None = None,
) -> str:
    """Translate a grounded English answer into fluent Devanagari Hindi."""
    text = english_answer.strip()
    if not text or is_devanagari(text):
        return english_answer

    user_note = ""
    if user_question and user_question.strip():
        user_note = (
            f"User question (may be Roman Hindi / Hinglish): {user_question.strip()}\n\n"
        )

    request = LLMRequest(
        system=_TRANSLATE_SYSTEM,
        user_message=(
            f"{user_note}"
            "English answer to translate:\n"
            f"{text}"
        ),
    )
    try:
        translated = (await llm.complete(request)).strip()
    except Exception:
        logger.exception("Hindi translation LLM call failed")
        return english_answer

    if not translated or not is_devanagari(translated):
        logger.warning("Hindi translation missing Devanagari — keeping English answer")
        return english_answer
    return translated
