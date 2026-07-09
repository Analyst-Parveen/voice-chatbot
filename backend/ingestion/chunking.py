"""Text chunking.

A lightweight recursive splitter (paragraphs → sentences → hard cut) with
overlap. Implemented directly rather than pulling in LangChain, keeping the
dependency surface small while producing sensible, retrieval-friendly chunks.
"""

from __future__ import annotations

import re

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_units(text: str) -> list[str]:
    """Break text into paragraphs, then oversized paragraphs into sentences."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        units.extend(s.strip() for s in _SENT_SPLIT.split(para) if s.strip())
    return units


def chunk_text(text: str, *, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into overlapping chunks of roughly ``chunk_size`` characters."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    units = _split_units(text)
    chunks: list[str] = []
    current = ""

    for unit in units:
        # A single unit longer than the window: hard-slice it.
        if len(unit) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(unit), chunk_size - overlap):
                chunks.append(unit[i : i + chunk_size].strip())
            continue

        if len(current) + len(unit) + 1 <= chunk_size:
            current = f"{current} {unit}".strip()
        else:
            chunks.append(current.strip())
            # Start next chunk with a tail overlap of the previous one.
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {unit}".strip()

    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]
