"""Ingestion pipeline: clean → chunk → embed → upsert into Qdrant.

Incremental by design: a manifest records a content hash per source, so only
changed or new sources are re-embedded, and sources that disappeared are deleted
from the vector store. This means the pipeline runs cheaply and "only when data
changes", as required.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from qdrant_client.models import PointStruct

from app.core.logging import get_logger
from app.rag.embedder import Embedder
from app.rag.vector_store import QdrantVectorStore, point_id
from ingestion.chunking import chunk_text
from ingestion.cleaning import clean_text
from ingestion.loaders.base import Document

logger = get_logger(__name__)


@dataclass
class IngestStats:
    sources_total: int = 0
    indexed: int = 0
    skipped: int = 0
    deleted: int = 0
    chunks_upserted: int = 0
    dry_run: bool = False
    details: list[str] = field(default_factory=list)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class IngestionPipeline:
    def __init__(
        self, embedder: Embedder, store: QdrantVectorStore, *, chunk_size: int = 800, overlap: int = 120
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._chunk_size = chunk_size
        self._overlap = overlap

    def _load_manifest(self, path: Path) -> dict[str, str]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_manifest(self, path: Path, manifest: dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def run(
        self,
        documents: list[Document],
        *,
        manifest_path: str | Path,
        recreate: bool = False,
        dry_run: bool = False,
    ) -> IngestStats:
        manifest_path = Path(manifest_path)
        stats = IngestStats(sources_total=len(documents), dry_run=dry_run)

        self._store.ensure_collection(self._embedder.dimension)
        if recreate and not dry_run:
            self._store.recreate(self._embedder.dimension)

        manifest = {} if recreate else self._load_manifest(manifest_path)
        seen: set[str] = set()

        for doc in documents:
            cleaned = clean_text(doc.text)
            if not cleaned:
                continue
            digest = _hash(cleaned)
            seen.add(doc.source)

            if manifest.get(doc.source) == digest and not recreate:
                stats.skipped += 1
                continue

            chunks = chunk_text(cleaned, chunk_size=self._chunk_size, overlap=self._overlap)
            if not chunks:
                continue

            if not dry_run:
                self._store.delete_by_source(doc.source)
                vectors = self._embedder.embed_texts(chunks)
                points = [
                    PointStruct(
                        id=point_id(doc.source, i),
                        vector=vec,
                        payload={
                            "text": chunk,
                            "source": doc.source,
                            "type": doc.type,
                            "url": doc.url,
                            "chunk_index": i,
                            "content_hash": digest,
                        },
                    )
                    for i, (chunk, vec) in enumerate(zip(chunks, vectors))
                ]
                self._store.upsert(points)

            manifest[doc.source] = digest
            stats.indexed += 1
            stats.chunks_upserted += len(chunks)
            stats.details.append(f"indexed {doc.source} ({len(chunks)} chunks)")

        # Delete sources that vanished since the last run.
        for stale in [s for s in manifest if s not in seen]:
            if not dry_run:
                self._store.delete_by_source(stale)
            del manifest[stale]
            stats.deleted += 1
            stats.details.append(f"deleted {stale}")

        if not dry_run:
            self._save_manifest(manifest_path, manifest)

        return stats
