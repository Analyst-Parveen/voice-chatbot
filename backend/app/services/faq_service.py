"""FAQ matching service — curated intent answers, no LLM at match time.

Embeds the (normalized) user query with the same model used at index time,
searches the dedicated FAQ Qdrant collection, and — on a confident hit — returns
the intent's pre-written answer directly. Falls through to ``None`` (RAG + LLM)
on any miss or error, so the FAQ layer can only help, never block.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories import FAQAnswerRepository, FAQIntentRepository
from app.rag.embedder import Embedder
from app.rag.vector_store import QdrantVectorStore
from app.services.dto import FAQMatch
from app.services.normalization import normalize_text

logger = get_logger(__name__)


def answer_language_for(language: str | None) -> str:
    """Which stored answer language to serve for a reply-language label."""
    return "hi" if (language or "").strip().lower() == "hindi" else "en"


class QdrantFAQService:
    """Real matcher backed by bge-m3 + a dedicated Qdrant collection."""

    def __init__(
        self, embedder: Embedder, store: QdrantVectorStore, threshold: float
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._threshold = threshold

    async def match(
        self, message: str, language: str | None, db: AsyncSession
    ) -> FAQMatch | None:
        try:
            normalized = normalize_text(message)
            if not normalized:
                return None
            vector = await asyncio.to_thread(self._embedder.embed_query, normalized)
            hits = await asyncio.to_thread(
                self._store.search, vector, 3, self._threshold
            )
            if not hits:
                return None
            answers = FAQAnswerRepository(db)
            intents = FAQIntentRepository(db)
            wanted = answer_language_for(language)
            for hit in hits:
                intent_key = (hit.get("payload") or {}).get("intent_key")
                if not intent_key:
                    continue
                intent = await intents.get_matchable(intent_key)
                if intent is None:
                    continue
                answer = await answers.get_for_intent(intent.id, wanted)
                if answer is None:
                    continue
                logger.info(
                    "FAQ hit: intent=%s confidence=%.3f lang=%s",
                    intent_key, hit["score"], wanted,
                )
                return FAQMatch(
                    intent_key=intent_key,
                    confidence=float(hit["score"]),
                    answer=answer.answer_text,
                    language=wanted,
                    sources=[s.source for s in intent.sources],
                )
            return None
        except Exception:
            logger.exception("FAQ match failed — falling through to RAG")
            return None


class StubFAQService:
    """No-op matcher (FAQ layer disabled / low-config mode)."""

    async def match(
        self, message: str, language: str | None, db: AsyncSession
    ) -> FAQMatch | None:
        return None


def build_faq_store(settings: Settings) -> QdrantVectorStore:
    """A vector store bound to the FAQ collection, sharing the RAG client."""
    from app.rag.vector_store import QdrantVectorStore, get_vector_store

    rag_store = get_vector_store(settings)
    return QdrantVectorStore(rag_store.client, settings.faq_collection)
