"""Ingestion CLI.

Discovers source files under a data directory (and optional website URLs),
loads/cleans/chunks/embeds them, and upserts into Qdrant. Incremental by default
(only changed sources are re-embedded).

Examples:
    python -m ingestion.run_ingestion --data-dir ./data
    python -m ingestion.run_ingestion --url https://example.com/faq --recreate
    python -m ingestion.run_ingestion --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.rag.embedder import get_embedder
from app.rag.vector_store import QdrantVectorStore
from ingestion.loaders.base import Document
from ingestion.loaders.docx_loader import load_docx
from ingestion.loaders.faq_loader import load_faq
from ingestion.loaders.pdf_loader import load_pdf
from ingestion.loaders.text_loader import load_text
from ingestion.loaders.website_loader import load_website
from ingestion.pipeline import IngestionPipeline

logger = get_logger("ingestion")

_TEXT_EXTS = {".txt", ".md", ".markdown"}
_FAQ_EXTS = {".json", ".yaml", ".yml"}


def discover(data_dir: Path) -> list[Document]:
    docs: list[Document] = []
    if not data_dir.exists():
        logger.warning("Data directory %s does not exist.", data_dir)
        return docs
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        ext = path.suffix.lower()
        try:
            if ext in _TEXT_EXTS:
                docs.append(load_text(path))
            elif ext in _FAQ_EXTS:
                docs.extend(load_faq(path))
            elif ext == ".pdf":
                docs.append(load_pdf(path))
            elif ext == ".docx":
                docs.append(load_docx(path))
        except Exception as exc:  # noqa: BLE001 - skip a bad file, keep going
            logger.error("Failed to load %s: %s", path, exc)
    return docs


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest knowledge into Qdrant.")
    parser.add_argument("--data-dir", default="./data", help="Directory of source files.")
    parser.add_argument("--url", action="append", default=[], help="Website URL(s) to ingest.")
    parser.add_argument("--recreate", action="store_true", help="Recreate the collection.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    parser.add_argument("--manifest", default=None, help="Path to the ingest manifest JSON.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=False)

    data_dir = Path(args.data_dir)
    manifest_path = Path(args.manifest) if args.manifest else data_dir / ".ingest_manifest.json"

    documents = discover(data_dir)
    for url in args.url:
        try:
            documents.append(load_website(url))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load %s: %s", url, exc)

    if not documents:
        logger.warning("No documents found to ingest.")
        return 0

    embedder = get_embedder(settings)
    store = QdrantVectorStore.from_settings(settings)
    pipeline = IngestionPipeline(embedder, store)

    logger.info(
        "Ingesting %d source(s) into collection '%s' (embedder=%s, dim=%d)…",
        len(documents), store.collection, getattr(embedder, "name", "?"), embedder.dimension,
    )
    stats = pipeline.run(
        documents, manifest_path=manifest_path, recreate=args.recreate, dry_run=args.dry_run
    )

    print(
        f"\n{'DRY RUN — ' if stats.dry_run else ''}Ingestion complete:\n"
        f"  sources:   {stats.sources_total}\n"
        f"  indexed:   {stats.indexed}\n"
        f"  skipped:   {stats.skipped} (unchanged)\n"
        f"  deleted:   {stats.deleted} (removed sources)\n"
        f"  chunks:    {stats.chunks_upserted} upserted\n"
        f"  total pts: {store.count()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
