"""FAQ loader.

Accepts JSON (or YAML, if pyyaml is installed) shaped as a list of
``{"question": "...", "answer": "..."}`` objects, or an object with a top-level
``faqs`` list. Each Q&A becomes its own document so retrieval can match a single
FAQ entry precisely.
"""

from __future__ import annotations

import json
from pathlib import Path

from ingestion.loaders.base import Document


def _parse(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                'YAML FAQ support needs pyyaml. Install with: pip install -e ".[ingest]"'
            ) from exc
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("faqs", [])
    return data if isinstance(data, list) else []


def load_faq(path: str | Path) -> list[Document]:
    p = Path(path)
    docs: list[Document] = []
    for i, entry in enumerate(_parse(p)):
        question = str(entry.get("question", "")).strip()
        answer = str(entry.get("answer", "")).strip()
        if not question and not answer:
            continue
        docs.append(
            Document(
                text=f"Q: {question}\nA: {answer}",
                source=f"{p}#{i}",
                type="faq",
                meta={"question": question},
            )
        )
    return docs
