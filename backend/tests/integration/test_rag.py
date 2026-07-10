"""RAG tests using the lexical embedder + in-memory Qdrant (no model downloads).

Covers the whole pipeline: embedding, chunking, ingestion (incremental),
retrieval, and grounded-vs-fallback behavior end-to-end through the
ConversationManager, including the retrieval audit trail in SQL.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.repositories import RetrievalRepository
from app.rag.embedder import LexicalEmbedder
from app.rag.reranker import NoopReranker
from app.rag.vector_store import QdrantVectorStore
from app.services.conversation_manager import ConversationManager
from app.services.memory_service import MemoryService
from app.services.telemetry_service import TelemetryService
from app.services.rag_service import QdrantRAGService
from app.services.stubs import StubLLMService
from app.services.validation_service import FALLBACK_MESSAGE, ValidationService
from ingestion.chunking import chunk_text
from ingestion.loaders.base import Document
from ingestion.pipeline import IngestionPipeline


def _rag_settings(**overrides) -> Settings:
    base = dict(
        RAG_ENABLED=True,
        EMBED_MODEL="lexical",
        RAG_USE_RERANKER=False,
        RAG_SCORE_THRESHOLD=0.15,
        RAG_MIN_CONTEXT_CHARS=10,
        RAG_TOP_K=3,
        DB_BACKEND="sqlite",
    )
    base.update(overrides)
    return Settings(**base)


# ---- Embedder & chunking ----

def test_lexical_embedder_overlap_similarity() -> None:
    emb = LexicalEmbedder()
    import numpy as np

    ret = np.array(emb.embed_query("what is your return policy"))
    doc_related = np.array(emb.embed_query("our return policy allows returns"))
    doc_unrelated = np.array(emb.embed_query("rocket launch to the moon"))
    assert float(ret @ doc_related) > float(ret @ doc_unrelated)


def test_chunking_overlap() -> None:
    text = "Sentence one. " * 200
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 220 for c in chunks)


# ---- Pipeline + retrieval ----

@pytest.fixture
def store() -> QdrantVectorStore:
    client = QdrantClient(location=":memory:")
    return QdrantVectorStore(client, "test_kb")


@pytest.fixture
def ingested(store: QdrantVectorStore, tmp_path) -> QdrantVectorStore:
    docs = [
        Document(
            text="Our return policy lets you return any product within 30 days "
            "for a full refund.",
            source="faq#return",
            type="faq",
        ),
        Document(
            text="Our business hours are Monday to Friday, 9 AM to 6 PM.",
            source="faq#hours",
            type="faq",
        ),
    ]
    pipeline = IngestionPipeline(LexicalEmbedder(), store)
    stats = pipeline.run(docs, manifest_path=tmp_path / "m.json")
    assert stats.indexed == 2
    assert store.count() == 2
    return store


def test_incremental_reindex_skips_unchanged(store: QdrantVectorStore, tmp_path) -> None:
    docs = [Document(text="hello world", source="a", type="text")]
    pipe = IngestionPipeline(LexicalEmbedder(), store)
    manifest = tmp_path / "m.json"
    first = pipe.run(docs, manifest_path=manifest)
    second = pipe.run(docs, manifest_path=manifest)
    assert first.indexed == 1
    assert second.indexed == 0 and second.skipped == 1


def test_removed_source_is_deleted(store: QdrantVectorStore, tmp_path) -> None:
    pipe = IngestionPipeline(LexicalEmbedder(), store)
    manifest = tmp_path / "m.json"
    pipe.run([Document(text="a doc", source="a", type="text")], manifest_path=manifest)
    stats = pipe.run([], manifest_path=manifest)  # source vanished
    assert stats.deleted == 1
    assert store.count() == 0


@pytest.mark.asyncio
async def test_rag_service_retrieves_relevant(ingested: QdrantVectorStore) -> None:
    rag = QdrantRAGService(
        embedder=LexicalEmbedder(),
        vector_store=ingested,
        reranker=NoopReranker(),
        settings=_rag_settings(),
    )
    chunks = await rag.retrieve("what is your return policy")
    assert chunks
    assert "return" in chunks[0].text.lower()


# ---- End-to-end through ConversationManager ----

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def _manager(db_session, store: QdrantVectorStore) -> ConversationManager:
    settings = _rag_settings()
    return ConversationManager(
        memory=MemoryService(db_session),
        llm=StubLLMService(),
        rag=QdrantRAGService(
            embedder=LexicalEmbedder(),
            vector_store=store,
            reranker=NoopReranker(),
            settings=settings,
        ),
        validation=ValidationService(settings),
        telemetry=TelemetryService(db_session),
        settings=settings,
    )


@pytest.mark.asyncio
async def test_grounded_answer_and_audit(db_session, ingested: QdrantVectorStore) -> None:
    manager = _manager(db_session, ingested)
    result = await manager.handle(session_id=None, message="what is your return policy")
    # In-domain: grounded, so the stub LLM answered (not the fallback) and
    # retrievals were logged.
    assert result.answer != FALLBACK_MESSAGE
    assert result.sources
    retrievals = await RetrievalRepository(db_session).list_by_message(result.message_id)
    assert retrievals
    assert any(r.used for r in retrievals)


@pytest.mark.asyncio
async def test_out_of_scope_returns_fallback(db_session, ingested: QdrantVectorStore) -> None:
    manager = _manager(db_session, ingested)
    result = await manager.handle(
        session_id=None, message="zorblax quibberflum wumpus gribbnok"
    )
    assert result.answer == FALLBACK_MESSAGE
