"""Offline FAQ generation CLI — one-time LLM use, never at runtime.

Reads company documents, asks the EXISTING Ollama LLM to propose intent Q&A in
English/Hindi/Hinglish, stores them (pending review) in the database, and
(re)builds the FAQ Qdrant collection from the DB. Kept out of the request path:
matching at runtime uses the pre-built vectors + stored answers only.

    python -m ingestion.generate_faqs --data-dir ../data/extracted --approve
    python -m ingestion.generate_faqs --reindex-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import uuid
from pathlib import Path

from qdrant_client.models import PointStruct
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import FAQAnswer, FAQIntent, FAQQuestion, FAQSource
from app.db.repositories import FAQIntentRepository
from app.db.session import get_sessionmaker
from app.services.dto import LLMRequest
from app.services.faq_service import build_faq_store
from app.services.normalization import normalize_text

logger = get_logger("ingestion.faq")

# Stable namespace so a question's vector id is deterministic across re-runs.
_FAQ_NAMESPACE = uuid.UUID("8c9de1f0-4b3a-4c2d-9e5f-1a2b3c4d5e6f")

_GENERATION_PROMPT = """You are building an FAQ knowledge base for a company assistant.
From the DOCUMENT below, extract the {count} most useful customer questions.

Return ONLY a JSON array. Each element must have exactly these keys:
- "intent_key": short snake_case id (e.g. "claim_process")
- "category": one word (e.g. "claims", "warranty", "contact", "company")
- "questions_en": list of 3 English phrasings
- "questions_hi": list of 2 Hindi (Devanagari) phrasings
- "questions_hinglish": list of 3 Roman-Hindi / WhatsApp-style phrasings
  (e.g. "claim kaise kare", "warranty kitni h")
- "answer_en": factual English answer, 2-4 sentences, ONLY from the document
- "answer_hi": the same answer in natural Hindi (Devanagari)

Rules: answers must come ONLY from the document — no outside knowledge.
If the document has no useful customer information, return [].

DOCUMENT ({source}):
{text}

JSON array:"""


def _extract_json_array(raw: str) -> list[dict]:
    """Tolerant JSON extraction (small local models add prose around JSON)."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _valid_item(item: dict) -> bool:
    try:
        return bool(
            isinstance(item, dict)
            and re.fullmatch(r"[a-z0-9_]{3,64}", item.get("intent_key", ""))
            and item.get("answer_en", "").strip()
            and item.get("answer_hi", "").strip()
            and (item.get("questions_en") or item.get("questions_hinglish"))
        )
    except Exception:
        return False


async def _generate_for_document(llm, source: str, text: str, count: int) -> list[dict]:
    prompt = _GENERATION_PROMPT.format(count=count, source=source, text=text[:6000])
    raw = await llm.complete(LLMRequest(user_message=prompt))
    items = [i for i in _extract_json_array(raw) if _valid_item(i)]
    logger.info("%s -> %d valid intents", source, len(items))
    return items


async def _store_intents(db, items: list[dict], source: str, approve: bool) -> int:
    """Upsert generated intents (idempotent per intent_key)."""
    repo = FAQIntentRepository(db)
    stored = 0
    for item in items:
        key = item["intent_key"].strip()
        existing = await repo.get_by_key(key)
        if existing is not None:
            continue
        intent = FAQIntent(
            intent_key=key,
            category=(item.get("category") or "general")[:64],
            status="approved" if approve else "pending",
            enabled=True,
        )
        db.add(intent)
        await db.flush()

        def _add_questions(texts, tag: str, quick: bool = False) -> None:
            for i, q in enumerate(texts or []):
                q = str(q).strip()[:512]
                if q:
                    db.add(
                        FAQQuestion(
                            intent_id=intent.id,
                            text=q,
                            language_tag=tag,
                            is_quick_question=quick and i == 0,
                        )
                    )

        _add_questions(item.get("questions_en"), "en", quick=True)
        _add_questions(item.get("questions_hi"), "hi", quick=True)
        _add_questions(item.get("questions_hinglish"), "hinglish")
        db.add(
            FAQAnswer(
                intent_id=intent.id, language="en",
                answer_text=str(item["answer_en"]).strip(),
            )
        )
        db.add(
            FAQAnswer(
                intent_id=intent.id, language="hi",
                answer_text=str(item["answer_hi"]).strip(),
            )
        )
        db.add(FAQSource(intent_id=intent.id, source=source))
        stored += 1
    return stored


async def _reindex(db, settings) -> int:
    """(Re)build the FAQ Qdrant collection from ALL intents in the DB.

    Vectors for every question variant, normalized exactly like match-time
    queries. Point ids are deterministic so re-runs overwrite cleanly.
    """
    from app.rag.embedder import get_embedder

    result = await db.execute(select(FAQQuestion))
    questions = list(result.scalars().all())
    if not questions:
        logger.warning("No FAQ questions in the database — nothing to index.")
        return 0

    intent_keys: dict[str, str] = {}
    for intent in (await db.execute(select(FAQIntent))).scalars().all():
        intent_keys[intent.id] = intent.intent_key

    embedder = get_embedder(settings)
    store = build_faq_store(settings)
    texts = [normalize_text(q.text) for q in questions]
    vectors = embedder.embed_texts(texts)
    store.recreate(len(vectors[0]))
    points = [
        PointStruct(
            id=str(uuid.uuid5(_FAQ_NAMESPACE, f"{q.id}")),
            vector=vec,
            payload={
                "intent_key": intent_keys.get(q.intent_id, ""),
                "question": q.text,
                "language_tag": q.language_tag,
            },
        )
        for q, vec in zip(questions, vectors)
    ]
    store.upsert(points)
    logger.info("Indexed %d question vectors into '%s'.", len(points), store.collection)
    return len(points)


async def main_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        if not args.reindex_only:
            from app.services.factory import get_llm_service

            llm = get_llm_service(settings)
            data_dir = Path(args.data_dir)
            files = sorted(
                p for p in data_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in {".md", ".markdown", ".txt"}
            )
            if not files:
                logger.warning("No .md/.txt documents under %s", data_dir)
            total = 0
            for path in files:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore").strip()
                    if len(text) < 200:
                        continue
                    items = await _generate_for_document(
                        llm, path.name, text, args.per_doc
                    )
                    total += await _store_intents(db, items, str(path), args.approve)
                    await db.commit()
                except Exception:
                    logger.exception("Generation failed for %s — skipping", path.name)
                    await db.rollback()
                    continue
            logger.info("Stored %d new intents.", total)
        indexed = await _reindex(db, settings)
        await db.commit()
        logger.info("Done. %d vectors in the FAQ collection.", indexed)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate + index FAQs (offline).")
    parser.add_argument(
        "--data-dir", default="../data/extracted", help="Folder of .md/.txt documents."
    )
    parser.add_argument(
        "--per-doc", type=int, default=4, help="Max intents to extract per document."
    )
    parser.add_argument(
        "--approve", action="store_true",
        help="Mark generated intents approved (matchable) immediately.",
    )
    parser.add_argument(
        "--reindex-only", action="store_true",
        help="Skip generation; rebuild Qdrant vectors from the DB.",
    )
    args = parser.parse_args()
    configure_logging(level="INFO")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
