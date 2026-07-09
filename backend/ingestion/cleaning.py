"""Text cleaning and normalization."""

from __future__ import annotations

import re
import unicodedata

_WS_RUN = re.compile(r"[ \t ]+")
_BLANKLINES = re.compile(r"\n{3,}")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_text(text: str) -> str:
    """Normalize unicode, strip control chars, and collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = _CTRL.sub("", text)
    # Normalize line endings, trim trailing spaces per line.
    lines = [_WS_RUN.sub(" ", line).rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    text = "\n".join(lines)
    text = _BLANKLINES.sub("\n\n", text)
    return text.strip()
