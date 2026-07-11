"""Input normalization for FAQ/intent matching.

Pure functions, no I/O, never raises. Applied to user queries BEFORE embedding
at match time AND to question variants BEFORE embedding at index time — the
same function on both sides, so the vectors compare like-for-like.

Handles: casing, punctuation, repeated characters, WhatsApp/Hinglish
shorthand, common Roman-Hindi spelling variants, and light STT artifacts.
Devanagari text passes through untouched (bge-m3 is multilingual).
"""

from __future__ import annotations

import re

# WhatsApp / SMS shorthand and abbreviations → their expanded form.
_EXPANSIONS: dict[str, str] = {
    "h": "hai",
    "hy": "hai",
    "kb": "kab",
    "kha": "kaha",
    "kaha": "kaha",
    "kyu": "kyun",
    "ky": "kya",
    "kr": "kar",
    "krna": "karna",
    "krne": "karne",
    "kro": "karo",
    "btao": "bata do",
    "btado": "bata do",
    "batao": "bata do",
    "bta": "bata",
    "plz": "please",
    "pls": "please",
    "u": "you",
    "ur": "your",
    "r": "are",
    "y": "why",
    "hw": "how",
    "abt": "about",
    "nd": "and",
    "thx": "thanks",
    "tel": "tell",
    "tl": "tell",
    "wht": "what",
    "wat": "what",
    "whts": "what is",
    "hai na": "hai",
    "wfh": "work from home",
    "cl": "casual leave",
    "pl": "privilege leave",
    "sl": "sick leave",
    "ew": "extended warranty",
    "sdp": "screen damage protection",
    "adp": "accidental damage protection",
    "cpp": "combo protection plan",
    "emi": "installment",
    "no.": "number",
    "num": "number",
    "tollfree": "toll free",
}

# Common Roman-Hindi / phonetic misspellings → a canonical spelling.
_ROMAN_HINDI: dict[str, str] = {
    "chutti": "chhutti",
    "chuti": "chhutti",
    "clame": "claim",
    "clam": "claim",
    "klaim": "claim",
    "garanti": "guarantee",
    "waranti": "warranty",
    "warrenty": "warranty",
    "warranti": "warranty",
    "polisy": "policy",
    "palicy": "policy",
    "policey": "policy",
    "rejister": "register",
    "registr": "register",
    "kampani": "company",
    "compny": "company",
    "ofis": "office",
    "offce": "office",
    "salry": "salary",
    "sarvice": "service",
    "servis": "service",
}

# Strip punctuation but keep word chars, whitespace, Devanagari, and dots.
_PUNCT_RE = re.compile(r"[^\w\sऀ-ॿ.]", re.UNICODE)
# Collapse a character repeated 3+ times down to one (e.g. "helllooo" -> "helo").
_REPEAT_RE = re.compile(r"(\w)\1{2,}")
_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize a query/question for semantic matching. Never raises."""
    try:
        out = (text or "").strip().lower()
        if not out:
            return ""
        out = _PUNCT_RE.sub(" ", out)
        out = _REPEAT_RE.sub(r"\1", out)
        words = out.split()
        expanded: list[str] = []
        for word in words:
            replacement = _EXPANSIONS.get(word) or _ROMAN_HINDI.get(word)
            expanded.append(replacement if replacement else word)
        out = " ".join(expanded)
        out = out.replace(".", " ")
        return _WS_RE.sub(" ", out).strip()
    except Exception:
        return (text or "").strip().lower()
