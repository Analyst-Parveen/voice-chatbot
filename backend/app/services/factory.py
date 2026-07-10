"""Service factory — binds interface → implementation by run mode.

Right now every mode uses the stub implementations (the real faster-whisper /
Piper / Ollama / Qdrant services arrive in Phases 6–7). When they do, extend the
``else`` branches here — nothing else in the app changes, because callers depend
only on the interfaces in ``interfaces.py``.

The AI services are stateless singletons (cached per process). ``MemoryService``
and ``ConversationManager`` are NOT cached — they are per-request because they
hold a database session.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.cache import AnswerCache
from app.services.conversation_manager import ConversationManager
from app.services.interfaces import LLMService, RAGService, STTService, TTSService
from app.services.memory_service import MemoryService
from app.services.telemetry_service import TelemetryService
from app.services.stubs import (
    StubLLMService,
    StubRAGService,
    StubSTTService,
    StubTTSService,
)
from app.services.validation_service import ValidationService

logger = get_logger(__name__)

_llm_service: LLMService | None = None
_stt_service: STTService | None = None
_tts_services: dict[str, TTSService] = {}


def get_llm_service(settings: Settings) -> LLMService:
    global _llm_service
    if _llm_service is None:
        if settings.is_stub:
            _llm_service = StubLLMService()
        else:
            from app.services.llm_ollama import OllamaLLMService

            _llm_service = OllamaLLMService(settings)
            logger.info("LLM: Ollama model=%s", settings.llm_model)
    return _llm_service


_rag_service: RAGService | None = None


def get_rag_service(settings: Settings) -> RAGService:
    """Real Qdrant-backed RAG when enabled; otherwise the no-op stub.

    Cached as a process singleton so the embedder/model loads at most once.
    """
    global _rag_service
    if _rag_service is None:
        if settings.rag_enabled:
            # Imported here so the qdrant/model imports only load when RAG is on.
            from app.rag.embedder import get_embedder
            from app.rag.reranker import get_reranker
            from app.rag.vector_store import get_vector_store
            from app.services.rag_service import QdrantRAGService

            _rag_service = QdrantRAGService(
                embedder=get_embedder(settings),
                vector_store=get_vector_store(settings),
                reranker=get_reranker(settings),
                settings=settings,
            )
            logger.info("RAG enabled (embed_model=%s).", settings.embed_model)
        else:
            _rag_service = StubRAGService()
    return _rag_service


def get_stt_service(settings: Settings) -> STTService:
    global _stt_service
    if _stt_service is None:
        if settings.is_stub:
            _stt_service = StubSTTService()
        else:
            from app.services.stt_whisper import WhisperSTTService

            _stt_service = WhisperSTTService(settings)
    return _stt_service


def get_tts_service(settings: Settings, voice: str | None = None) -> TTSService:
    voice_key = voice or settings.piper_voice
    if voice_key not in _tts_services:
        if settings.is_stub:
            _tts_services[voice_key] = StubTTSService()
        else:
            from app.services.tts_piper import PiperTTSService

            _tts_services[voice_key] = PiperTTSService(settings, voice=voice_key)
    return _tts_services[voice_key]


def get_tts_for_language(settings: Settings, language: str | None) -> TTSService:
    from app.services.tts_piper import resolve_voice_for_language

    voice = resolve_voice_for_language(language, settings)
    return get_tts_service(settings, voice=voice)


def build_conversation_manager(db_session, settings: Settings) -> ConversationManager:
    """Assemble a ConversationManager for one request/turn."""
    return ConversationManager(
        memory=MemoryService(db_session),
        llm=get_llm_service(settings),
        rag=get_rag_service(settings),
        validation=ValidationService(settings),
        telemetry=TelemetryService(db_session),
        settings=settings,
        cache=AnswerCache(settings),
    )
