"""PDF loader (lazy pypdf import)."""

from __future__ import annotations

from pathlib import Path

from ingestion.loaders.base import Document


def load_pdf(path: str | Path) -> Document:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - optional extra
        raise RuntimeError(
            'PDF support needs pypdf. Install with: pip install -e ".[ingest]"'
        ) from exc
    p = Path(path)
    reader = PdfReader(str(p))
    pages = [page.extract_text() or "" for page in reader.pages]
    return Document(text="\n\n".join(pages), source=str(p), type="pdf")
