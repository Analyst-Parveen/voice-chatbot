"""Plain text / Markdown loader (dependency-free)."""

from __future__ import annotations

from pathlib import Path

from ingestion.loaders.base import Document


def load_text(path: str | Path) -> Document:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    return Document(text=text, source=str(p), type="text")
