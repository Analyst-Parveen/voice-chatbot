"""In-memory per-client rate limiting (free, no Redis).

A fixed-window counter keyed by client IP. The limit comes from
``RATE_LIMIT_PER_MINUTE``. This is intentionally dependency-free so it works on
a low-config PC and in a single-container deployment.

SCALING NOTE: in-memory state is per-process. If you run multiple backend
replicas behind a load balancer, move this to a shared store (e.g. Redis) so
the limit is global. The middleware interface stays the same.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger, get_request_id

logger = get_logger(__name__)


class _FixedWindowCounter:
    """Thread-safe fixed-window request counter per key."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, remaining) for this key."""
        now = time.monotonic()
        with self._lock:
            count, window_start = self._hits[key]
            if now - window_start >= self.window:
                # New window.
                self._hits[key] = (1, now)
                return True, self.limit - 1
            if count >= self.limit:
                return False, 0
            self._hits[key] = (count + 1, window_start)
            return True, self.limit - (count + 1)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests exceeding the per-minute limit with HTTP 429.

    Excludes health/docs so monitoring and the OpenAPI UI are never throttled.

    When ``redis_url`` is provided the counter is shared across replicas via
    Redis (INCR + per-minute expiry); otherwise it stays in-process. Any Redis
    error degrades gracefully to the in-memory counter so a Redis hiccup never
    starts rejecting traffic.
    """

    _EXCLUDED_PREFIXES = ("/api/health", "/metrics", "/docs", "/openapi.json", "/redoc")

    def __init__(self, app, limit_per_minute: int, redis_url: str = "") -> None:
        super().__init__(app)
        self._counter = _FixedWindowCounter(limit=max(1, limit_per_minute))
        self._redis = None
        if redis_url:
            try:
                from redis.asyncio import from_url

                self._redis = from_url(redis_url, decode_responses=True)
                logger.info("Rate limiting via Redis.")
            except Exception:  # noqa: BLE001
                logger.exception("Redis unavailable for rate limiting — using in-memory")

    def _client_key(self, request: Request) -> str:
        # Honor a reverse-proxy forwarded IP when present (Phase 8 nginx).
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _allow(self, key: str) -> tuple[bool, int]:
        """Shared Redis counter when configured; else the in-memory counter."""
        if self._redis is None:
            return self._counter.allow(key)
        limit = self._counter.limit
        bucket = f"rl:{key}:{int(time.time() // 60)}"
        try:
            count = await self._redis.incr(bucket)
            if count == 1:
                await self._redis.expire(bucket, 60)
            if count > limit:
                return False, 0
            return True, limit - count
        except Exception:  # noqa: BLE001
            return self._counter.allow(key)  # fall back on Redis error

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path.startswith(self._EXCLUDED_PREFIXES):
            return await call_next(request)

        key = self._client_key(request)
        allowed, remaining = await self._allow(key)
        if not allowed:
            logger.info("Rate limit exceeded for %s on %s", key, path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Please slow down.",
                        "details": {"limit_per_minute": self._counter.limit},
                        "request_id": get_request_id(),
                    }
                },
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._counter.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
