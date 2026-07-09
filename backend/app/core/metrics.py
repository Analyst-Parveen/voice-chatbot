"""Prometheus metrics.

Defines the app's metrics on a dedicated registry and a middleware that records
HTTP request counts and latency. Business metrics (conversation turns, errors,
active WebSocket connections) are incremented from the relevant code paths.

Exposed at ``GET /metrics`` in Prometheus text format — scrape it with
Prometheus/Grafana, or just ``curl`` it.
"""

from __future__ import annotations

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Dedicated registry (keeps our metrics isolated and avoids global-default clashes).
REGISTRY = CollectorRegistry()

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests.",
    ["method", "path", "status"], registry=REGISTRY,
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request latency (seconds).",
    ["method", "path"], registry=REGISTRY,
)
conversation_turns_total = Counter(
    "conversation_turns_total", "Conversation turns handled.",
    ["channel", "outcome"], registry=REGISTRY,  # outcome: answered | fallback
)
conversation_turn_duration_seconds = Histogram(
    "conversation_turn_duration_seconds", "Conversation turn latency (seconds).",
    ["channel"], registry=REGISTRY,
)
app_errors_total = Counter(
    "app_errors_total", "Application errors by code.",
    ["code"], registry=REGISTRY,
)
ws_active_connections = Gauge(
    "ws_active_connections", "Active WebSocket connections.",
    ["endpoint"], registry=REGISTRY,
)


def render() -> bytes:
    return generate_latest(REGISTRY)


CONTENT_TYPE = CONTENT_TYPE_LATEST


def record_turn(channel: str, *, fallback: bool, latency_ms: int) -> None:
    """Record one completed conversation turn."""
    conversation_turns_total.labels(
        channel=channel, outcome="fallback" if fallback else "answered"
    ).inc()
    conversation_turn_duration_seconds.labels(channel=channel).observe(latency_ms / 1000.0)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Count HTTP requests and observe their latency, keyed by route template
    (not raw path) to avoid unbounded label cardinality from ids."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        http_requests_total.labels(request.method, path, str(response.status_code)).inc()
        http_request_duration_seconds.labels(request.method, path).observe(elapsed)
        return response
