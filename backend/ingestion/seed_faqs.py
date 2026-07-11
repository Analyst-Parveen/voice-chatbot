"""Fast FAQ seed — load curated intents from JSON (no LLM).

Use this instead of ``generate_faqs`` when you already have reviewed Q&A
content. Typical run (< 1 minute):

    python -m ingestion.seed_faqs
    python -m ingestion.seed_faqs --file ../data/faq_seed.json

Stop the backend first if using embedded Qdrant (same rule as run_ingestion).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_sessionmaker
from ingestion.generate_faqs import _reindex, _store_intents, _valid_item

logger = get_logger("ingestion.seed_faqs")


def _load_seed(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("intents", data.get("faqs", []))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    items = [i for i in data if _valid_item(i)]
    logger.info("Loaded %d / %d valid intents from %s", len(items), len(data), path.name)
    return items


async def main_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    seed_path = Path(args.file)
    if not seed_path.exists():
        logger.error("Seed file not found: %s", seed_path)
        return 1

    items = _load_seed(seed_path)
    if not items:
        logger.error("No valid intents in seed file.")
        return 1

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        stored = await _store_intents(db, items, str(seed_path), approve=args.approve)
        await db.commit()
        logger.info("Stored %d new intents (skipped existing keys).", stored)
        indexed = await _reindex(db, settings)
        await db.commit()
        logger.info("Done. %d vectors indexed into '%s'.", indexed, settings.faq_collection)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed FAQ intents from curated JSON.")
    parser.add_argument(
        "--file",
        default="../data/faq_seed.json",
        help="Curated intent JSON (array of intent objects).",
    )
    parser.add_argument(
        "--pending",
        action="store_true",
        help="Store as pending (not matchable until admin approves).",
    )
    args = parser.parse_args()
    args.approve = not args.pending
    configure_logging(level="INFO")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
