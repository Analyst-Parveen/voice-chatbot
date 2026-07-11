"""FAQ loader.

Accepts JSON (or YAML, if pyyaml is installed) in either of two shapes:

1. Simple Q&A — a list of ``{"question": "...", "answer": "..."}`` objects
   (or an object with a top-level ``faqs`` list).
2. Rich multilingual intents — a list of objects with ``questions_en`` /
   ``questions_hi`` / ``questions_hinglish`` phrasing variants and
   ``answer_en`` / ``answer_hi`` answers (or an object with a top-level
   ``intents`` list). This is the ``faq_seed.json`` format.

Each Q&A / intent becomes its own document so retrieval can match a single FAQ
entry precisely. For rich intents we fold every question phrasing into the
document text so a query in any language/script matches the same answer.
"""

from __future__ import annotations

import json
from pathlib import Path

from ingestion.loaders.base import Document

# Keys that mark the rich multilingual intent schema (faq_seed.json).
_QUESTION_KEYS = ("questions_en", "questions_hi", "questions_hinglish")
_ANSWER_KEYS = ("answer_en", "answer_hi")


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
        # Support both {"faqs": [...]} (simple) and {"intents": [...]} (rich).
        data = data.get("intents", data.get("faqs", []))
    return data if isinstance(data, list) else []


def _is_rich_intent(entry: dict) -> bool:
    return any(k in entry for k in _QUESTION_KEYS) or any(k in entry for k in _ANSWER_KEYS)


def _collect_strings(value: object) -> list[str]:
    """Flatten a value that may be a string or a list of strings."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _rich_intent_document(entry: dict, path: Path, index: int) -> Document | None:
    """Turn a multilingual intent object into a single retrieval document."""
    questions: list[str] = []
    for key in _QUESTION_KEYS:
        questions.extend(_collect_strings(entry.get(key)))
    questions.extend(_collect_strings(entry.get("question")))  # tolerate mixed files

    answers: list[str] = []
    for key in _ANSWER_KEYS:
        answers.extend(_collect_strings(entry.get(key)))
    answers.extend(_collect_strings(entry.get("answer")))

    if not questions and not answers:
        return None

    # Every phrasing goes into the text so a query in any language/script scores
    # highly against this entry; both answers give the LLM grounded content.
    text = "Q: " + " / ".join(questions) + "\nA: " + "\n".join(answers)
    intent_key = str(entry.get("intent_key", index)).strip() or str(index)
    meta = {"question": questions[0] if questions else ""}
    category = str(entry.get("category", "")).strip()
    if category:
        meta["category"] = category
    return Document(
        text=text,
        source=f"{path}#{intent_key}",
        type="faq",
        meta=meta,
    )


def _simple_document(entry: dict, path: Path, index: int) -> Document | None:
    question = str(entry.get("question", "")).strip()
    answer = str(entry.get("answer", "")).strip()
    if not question and not answer:
        return None
    return Document(
        text=f"Q: {question}\nA: {answer}",
        source=f"{path}#{index}",
        type="faq",
        meta={"question": question},
    )


def load_faq(path: str | Path) -> list[Document]:
    p = Path(path)
    docs: list[Document] = []
    for i, entry in enumerate(_parse(p)):
        if not isinstance(entry, dict):
            continue
        doc = (
            _rich_intent_document(entry, p, i)
            if _is_rich_intent(entry)
            else _simple_document(entry, p, i)
        )
        if doc is not None:
            docs.append(doc)
    return docs
