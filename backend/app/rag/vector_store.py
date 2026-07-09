"""Qdrant vector store wrapper.

Abstracts collection management and search so the rest of the app never touches
the Qdrant SDK directly. Works in three modes, chosen by settings:

- server mode   — ``QDRANT_URL`` set (docker-full): connects to the Qdrant service
- embedded mode — ``QDRANT_PATH`` set (local-light): on-disk, no server needed
- in-memory     — ``:memory:`` (tests)

All three use the same code path — the only difference is how the client is
constructed.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def point_id(source: str, chunk_index: int) -> str:
    """Deterministic point id so re-ingesting a source overwrites its points."""
    return str(uuid.uuid5(_NAMESPACE, f"{source}:{chunk_index}"))


class QdrantVectorStore:
    def __init__(self, client: QdrantClient, collection: str) -> None:
        self.client = client
        self.collection = collection

    @classmethod
    def from_settings(cls, settings: Settings) -> "QdrantVectorStore":
        if settings.qdrant_url:
            client = QdrantClient(url=settings.qdrant_url)
        elif settings.qdrant_path == ":memory:":
            client = QdrantClient(location=":memory:")
        else:
            client = QdrantClient(path=settings.qdrant_path)
        return cls(client, settings.qdrant_collection)

    def exists(self) -> bool:
        return self.client.collection_exists(self.collection)

    def ensure_collection(self, dim: int) -> None:
        if not self.exists():
            self.client.create_collection(
                self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def recreate(self, dim: int) -> None:
        if self.exists():
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            self.collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    def upsert(self, points: list[PointStruct]) -> None:
        if points:
            self.client.upsert(self.collection, points=points)

    def delete_by_source(self, source: str) -> None:
        self.client.delete(
            self.collection,
            points_selector=Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=source))]
            ),
        )

    def search(
        self, vector: list[float], top_k: int, score_threshold: float | None = None
    ) -> list[dict]:
        if not self.exists():
            return []
        response = self.client.query_points(
            self.collection,
            query=vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {"id": str(h.id), "score": float(h.score), "payload": h.payload or {}}
            for h in response.points
        ]

    def count(self) -> int:
        if not self.exists():
            return 0
        return int(self.client.count(self.collection).count)


_store: QdrantVectorStore | None = None


def get_vector_store(settings: Settings) -> QdrantVectorStore:
    """Process-wide vector store singleton."""
    global _store
    if _store is None:
        _store = QdrantVectorStore.from_settings(settings)
        logger.info("Qdrant vector store ready (collection=%s)", _store.collection)
    return _store
