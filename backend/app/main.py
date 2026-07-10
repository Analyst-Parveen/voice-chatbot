"""FastAPI application factory.

Phase 2 wires the configuration layer into a production-shaped app:
structured logging, request-context (correlation ids) + access logging,
in-memory rate limiting, CORS from config, and global exception handlers.
A lifespan hook logs startup/shutdown and is where later phases initialize the
DB engine, Qdrant, and Ollama clients (and dispose of them cleanly).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.rest import chat, feedback, health, helpdesk, history, metrics, preferences, session, suggestions
from app.api.ws import chat_ws, voice_ws
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.metrics import MetricsMiddleware
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.security import build_cors_kwargs
from app.db.session import dispose_engine, ping_database

logger = get_logger("voiceai")


async def _warm_up_models(settings: Settings) -> None:
    """Load heavy AI singletons at startup instead of on the first user turn.

    On a low-config CPU the embedder and Ollama model take tens of seconds to
    load the first time. If that happens lazily during the first turn it blocks
    the event loop past the WebSocket keepalive timeout, so the client's socket
    drops and the UI spins forever. Warming here (before any client connects)
    keeps the first real turn responsive. Failures are non-fatal — the lazy
    path still works, just slower.
    """
    if settings.is_stub:
        return  # stubs are instant; nothing to warm.
    from app.services.dto import LLMRequest
    from app.services.factory import get_llm_service, get_rag_service, get_tts_for_language

    start = time.perf_counter()
    try:
        if settings.rag_enabled:
            rag = get_rag_service(settings)
            await rag.retrieve("warmup")  # loads the embedder + opens the vector store
        llm = get_llm_service(settings)
        await llm.complete(LLMRequest(user_message="hi"))  # loads the Ollama model into RAM
        try:
            await get_tts_for_language(settings, None).synthesize("ok")  # loads Piper voice
        except Exception:
            logger.warning("TTS warm-up skipped (unavailable)")
        logger.info("Model warm-up complete in %.1fs", time.perf_counter() - start)
    except Exception:
        logger.exception("Model warm-up failed (continuing; first turn will be slower)")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks.

    Later phases initialize the DB engine, Qdrant client, Ollama client, and
    model warm-up here, and dispose of them on shutdown.
    """
    settings = get_settings()
    logger.info(
        "Starting %s v%s | run_mode=%s | env=%s | db=%s",
        settings.app_name,
        __version__,
        settings.run_mode.value,
        settings.app_env,
        settings.db_backend.value,
    )
    # Non-fatal DB probe so startup surfaces connectivity issues early.
    db_ok = await ping_database()
    logger.info("Database connectivity: %s", "ok" if db_ok else "unreachable")

    # Warm the heavy AI models now so the first user turn isn't a cold load
    # that blocks the event loop and drops the WebSocket.
    await _warm_up_models(settings)

    yield

    await dispose_engine()
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    app = FastAPI(
        title="Voice AI Assistant API",
        version=__version__,
        description="Self-hosted Voice + Text AI Assistant (RAG-grounded, 100% free).",
        lifespan=lifespan,
    )

    # Middleware. Order matters: the last added runs outermost, so the request
    # context (and its request id) wraps everything, including rate limiting.
    app.add_middleware(
        RateLimitMiddleware,
        limit_per_minute=settings.rate_limit_per_minute,
        redis_url=settings.redis_url,
    )
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(CORSMiddleware, **build_cors_kwargs(settings))
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    # REST routers (all under /api).
    app.include_router(health.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(feedback.router, prefix="/api")
    app.include_router(session.router, prefix="/api")
    app.include_router(preferences.router, prefix="/api")
    app.include_router(suggestions.router, prefix="/api")
    app.include_router(helpdesk.router, prefix="/api")

    # Metrics at root /metrics (Prometheus convention).
    app.include_router(metrics.router)

    # WebSocket routers (no /api prefix; they define /ws/* paths).
    app.include_router(chat_ws.router)
    app.include_router(voice_ws.router)

    @app.get("/", tags=["root"], summary="Service banner")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": __version__,
            "run_mode": settings.run_mode.value,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
