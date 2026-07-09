"""Rerankers — reorder retrieved chunks by query relevance.

- ``NoopReranker`` — keeps the vector-similarity order (used with the lexical
  embedder and in stub/dev mode).
- ``BgeReranker`` — the real ``BAAI/bge-reranker-v2-m3`` cross-encoder, which is
  far more accurate than pure vector similarity. Heavy; imported lazily.

Both return chunks with ``score`` normalized to roughly 0..1 so the grounding
threshold in ValidationService stays meaningful regardless of which is used.
"""

from __future__ import annotations

import math
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.dto import RetrievedChunk

logger = get_logger(__name__)


class Reranker(Protocol):
    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]: ...


class NoopReranker:
    """Sort by existing similarity score and truncate."""

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]


class BgeReranker:
    """Cross-encoder reranker (BAAI/bge-reranker-v2-m3)."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                "sentence-transformers is not installed. Install with "
                '"pip install -e \\".[embeddings]\\"" or set RAG_USE_RERANKER=false.'
            ) from exc
        logger.info("Loading reranker %s…", model_name)
        self._model = CrossEncoder(model_name)

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        scores = self._model.predict([(query, c.text) for c in chunks])
        for chunk, score in zip(chunks, scores):
            chunk.score = 1.0 / (1.0 + math.exp(-float(score)))  # sigmoid → 0..1
        return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]


def get_reranker(settings: Settings) -> Reranker:
    """Select the reranker for the current configuration."""
    if settings.is_stub or not settings.rag_use_reranker:
        return NoopReranker()
    return BgeReranker(settings.reranker_model)
