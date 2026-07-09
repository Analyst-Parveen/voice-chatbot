"""Dependency health checks.

Reports the status of each downstream dependency for the ``/api/health``
endpoint. Checks are cheap and dependency-free (stdlib TCP probe), so they are
safe to call on every health request and on a low-config PC.

Status vocabulary:
- ``ok``          reachable / usable
- ``unreachable`` configured but not responding
- ``disabled``    not used in the current run mode (e.g. stub)
- ``embedded``    runs in-process (embedded Qdrant / SQLite), nothing to probe
- ``not-checked`` live probe deferred to a later phase (e.g. DB in Phase 3)
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse

from app.core.config import DBBackend, Settings


def _tcp_ok(url: str, timeout: float = 1.0) -> bool:
    """Return True if a TCP connection to the URL's host:port succeeds."""
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_dependencies(settings: Settings) -> dict[str, str]:
    """Probe each dependency and return a name -> status map."""
    statuses: dict[str, str] = {}

    # --- Database ---
    if settings.use_sqlite:
        statuses["database"] = "embedded"  # SQLite file; real check in Phase 3
    else:
        host, port = settings.mssql_host, settings.mssql_port
        statuses["database"] = "ok" if _tcp_ok(f"tcp://{host}:{port}") else "unreachable"

    # --- Qdrant ---
    if settings.is_stub:
        statuses["qdrant"] = "disabled"
    elif settings.qdrant_url:
        statuses["qdrant"] = "ok" if _tcp_ok(settings.qdrant_url) else "unreachable"
    else:
        statuses["qdrant"] = "embedded"  # local on-disk mode (local-light)

    # --- Ollama (LLM) ---
    if settings.is_stub:
        statuses["ollama"] = "disabled"
    else:
        statuses["ollama"] = "ok" if _tcp_ok(settings.ollama_url) else "unreachable"

    return statuses


def overall_status(dependencies: dict[str, str]) -> str:
    """Aggregate dependency statuses into an overall service status."""
    if any(v == "unreachable" for v in dependencies.values()):
        return "degraded"
    return "ok"
