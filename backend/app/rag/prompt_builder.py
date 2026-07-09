"""Prompt construction — the anti-hallucination system prompt and context format."""

from __future__ import annotations

import re

from app.services.dto import RetrievedChunk
from app.services.validation_service import FALLBACK_MESSAGE, hindi_fallback_message

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_LATIN = re.compile(r"[A-Za-z]")
_HINGLISH_MARKERS = re.compile(
    r"\b(aap|apka|apke|kya|hai|hain|nahi|nahin|mein|main|kaise|ka|ki|ke|ko|se|par|"
    r"aur|yeh|ye|woh|hum|tum|batao|bataye|bata|karo|chahiye|mujhe|kripya|"
    r"dhanyawad|shukriya|namaste|kahan|kab|kyun|kaun|kitna|kitne)\b",
    re.I,
)


def detect_script_hint(message: str, language: str | None) -> str | None:
    """Tell the LLM which Hindi script/style the user is using."""
    if language != "Hindi":
        return None
    if _DEVANAGARI.search(message):
        return (
            "The user writes in Devanagari Hindi — reply in Devanagari Hindi only. "
            "Never use English sentences."
        )
    if _HINGLISH_MARKERS.search(message):
        return (
            "The user writes in Roman Hindi / Hinglish (WhatsApp chat style) — reply in "
            "the SAME Roman Hinglish style. Do not switch to Devanagari unless the user did."
        )
    if _LATIN.search(message):
        return (
            "The user selected Hindi but typed in English/Latin script. Still reply in Hindi "
            "(Roman Hinglish like WhatsApp, e.g. 'Main aapki madad kar sakta hoon') or "
            "Devanagari — never reply in English."
        )
    return (
        "The user selected Hindi. Reply in simple Hindi (Devanagari or Roman Hinglish). "
        "Never reply in English."
    )


def build_system_prompt(
    language: str | None = None,
    script_hint: str | None = None,
) -> str:
    fallback = hindi_fallback_message() if language == "Hindi" else FALLBACK_MESSAGE

    base = (
        "You are a helpful company assistant. Answer the user's question using ONLY "
        "the information in the CONTEXT section. Do not use prior knowledge. "
        "Do not describe yourself as a generic AI, Alibaba Cloud, OpenAI, or any vendor. "
        "If the answer is not contained in the context, reply with exactly: "
        f'"{fallback}" '
        "Never invent facts, prices, policies, URLs, phone numbers, or contact details. "
        "Be concise, accurate, and conversational."
    )

    if language == "Hindi":
        rules = (
            "LANGUAGE RULE (highest priority): The user chose Hindi. Every word of your "
            "reply MUST be in Hindi — Devanagari or Roman Hinglish. English replies are forbidden. "
            f"{base} "
            "Use simple, natural Hindi. Stay strictly grounded in CONTEXT. "
            "For Roman Hinglish: WhatsApp-style spelling (aap, kya, hai, nahi, ke baare mein). "
            "For Devanagari: correct Hindi grammar."
        )
    elif language == "English":
        rules = (
            f"{base} "
            "The user selected English. Reply only in clear, simple Indian English. "
            "Use polite, professional tone suitable for a company helpdesk."
        )
    else:
        rules = (
            f"{base} Always respond in the same language and script the user used."
        )

    if script_hint:
        rules = f"{rules} {script_hint}"
    return rules


def wrap_user_message(message: str, language: str | None) -> str:
    """Reinforce language choice in the user turn (helps small local LLMs)."""
    if language == "Hindi":
        return (
            "Reply in Hindi only (Devanagari or Roman Hinglish — NOT English).\n\n"
            f"User question: {message}"
        )
    if language == "English":
        return f"Reply in English only.\n\nUser question: {message}"
    return message


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks into a labeled CONTEXT block for the prompt."""
    if not chunks:
        return ""
    blocks = [f"[Source: {c.source}]\n{c.text.strip()}" for c in chunks]
    return "CONTEXT:\n" + "\n\n---\n\n".join(blocks)
