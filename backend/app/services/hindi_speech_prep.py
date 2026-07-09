"""Prepare Hindi text for Piper TTS (expects Devanagari for best pronunciation)."""

from __future__ import annotations

import re

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_LATIN = re.compile(r"[A-Za-z]")
_HINGLISH_MARKERS = re.compile(
    r"\b(aap|apka|apke|kya|hai|hain|nahi|nahin|mein|main|kaise|ka|ki|ke|ko|se|par|"
    r"aur|yeh|ye|woh|hum|tum|batao|bataye|bata|karo|chahiye|mujhe|kripya|"
    r"dhanyawad|shukriya|namaste|kahan|kab|kyun|kaun|kitna|kitne|jaankari|madad)\b",
    re.I,
)


def is_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text))


def is_roman_hindi(text: str) -> bool:
    return bool(_LATIN.search(text)) and not is_devanagari(text)


def classify_tts_script(text: str) -> str:
    """Classify text for TTS: devanagari | hinglish | english."""
    if is_devanagari(text):
        return "devanagari"
    if not _LATIN.search(text):
        return "devanagari"
    if _HINGLISH_MARKERS.search(text):
        return "hinglish"
    return "english"


def prepare_for_hindi_tts(text: str) -> str:
    """Convert Roman Hinglish to Devanagari for clear Hindi speech."""
    if not text.strip() or is_devanagari(text):
        return text
    script = classify_tts_script(text)
    if script != "hinglish":
        return text
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate

        return transliterate(text, sanscript.ITRANS, sanscript.DEVANAGARI)
    except Exception:
        return text
