"""Optional Redis client + grounded-answer cache.

Design contract: **Redis is always optional.** When ``REDIS_URL`` is empty (the
low-config local default) :func:`get_redis` returns ``None`` and every cache
operation is a no-op, so behavior is byte-for-byte identical to having no Redis.
On the server, set ``REDIS_URL`` to enable caching of grounded answers so
repeated questions skip the (expensive) LLM call.

Every Redis call is wrapped: a connection drop or error degrades to "cache
miss", never an exception — a Redis outage must not break a conversation turn.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Process-wide singleton. ``_initialized`` distinguishes "not tried yet" from
# "tried and unavailable" so we only build/log once.
_redis_client: Any | None = None
_initialized = False


def get_redis(settings: Settings) -> Any | None:
    """Return a shared async Redis client, or ``None`` when disabled/unavailable."""
    global _redis_client, _initialized
    if _initialized:
        return _redis_client
    _initialized = True
    if not settings.redis_url:
        _redis_client = None
        return None
    try:
        from redis.asyncio import from_url

        _redis_client = from_url(settings.redis_url, decode_responses=True)
        logger.info("Redis cache enabled (%s).", settings.redis_url)
    except Exception:  # noqa: BLE001 — missing package or bad URL: run without cache.
        logger.exception("Redis unavailable — continuing without cache")
        _redis_client = None
    return _redis_client


class AnswerCache:
    """Caches finalized answers keyed by (model, language, question, chunk ids).

    The retrieved chunk ids are part of the key so a knowledge-base re-ingest
    (which changes retrieval) naturally invalidates stale answers.
    """

    def __init__(self, settings: Settings) -> None:
        self._redis = get_redis(settings)
        self._ttl = settings.cache_ttl_seconds
        self._model = settings.llm_model

    @property
    def enabled(self) -> bool:
        return self._redis is not None and self._ttl > 0

    def _key(self, message: str, chunk_ids: list[str], language: str | None) -> str:
        norm = " ".join(message.lower().split())
        raw = "|".join([self._model, language or "", norm, *sorted(chunk_ids)])
        return "ans:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def get(
        self, message: str, chunk_ids: list[str], language: str | None
    ) -> str | None:
        if not self.enabled:
            return None
        try:
            return await self._redis.get(self._key(message, chunk_ids, language))
        except Exception:  # noqa: BLE001
            logger.warning("answer cache get failed; treating as miss")
            return None

    async def set(
        self, message: str, chunk_ids: list[str], language: str | None, answer: str
    ) -> None:
        if not self.enabled or not answer:
            return
        try:
            await self._redis.set(
                self._key(message, chunk_ids, language), answer, ex=self._ttl
            )
        except Exception:  # noqa: BLE001
            logger.warning("answer cache set failed; skipping")
