"""QdrantRAGService — real retrieval-augmented generation.

Pipeline: embed the query → vector search in Qdrant → rerank → return the top
chunks. CPU-bound model calls run in a thread so the event loop is never
blocked. Implements the ``RAGService`` protocol used by the ConversationManager,
so it drops in wherever the stub was.
"""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.core.logging import get_logger
from app.rag.embedder import Embedder
from app.rag.prompt_builder import format_context
from app.rag.reranker import Reranker
from app.rag.vector_store import QdrantVectorStore
from app.services.dto import RetrievedChunk

logger = get_logger(__name__)


class QdrantRAGService:
    def __init__(
        self,
        *,
        embedder: Embedder,
        vector_store: QdrantVectorStore,
        reranker: Reranker,
        settings: Settings,
    ) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._reranker = reranker
        self._settings = settings

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        if not self._store.exists():
            logger.debug("Knowledge collection is empty; no retrieval.")
            return []

        top_k = self._settings.rag_top_k
        # Over-fetch when reranking so the cross-encoder has candidates to sort.
        pool = top_k * 4 if self._settings.rag_use_reranker else top_k

        vector = await asyncio.to_thread(self._embedder.embed_query, query)
        hits = await asyncio.to_thread(self._store.search, vector, pool)

        chunks = [
            RetrievedChunk(
                chunk_id=h["id"],
                source=str(h["payload"].get("source", "unknown")),
                score=h["score"],
                text=str(h["payload"].get("text", "")),
            )
            for h in hits
        ]
        if not chunks:
            return []

        ranked = await asyncio.to_thread(
            self._reranker.rerank, query, chunks, top_k
        )
        return ranked

    def build_context(self, chunks: list[RetrievedChunk]) -> str:
        return format_context(chunks)
