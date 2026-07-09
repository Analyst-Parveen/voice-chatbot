"""Structured logging.

Two formats, chosen by ``LOG_JSON``:
- console (human-readable) for local dev,
- JSON (one object per line) for production log aggregation.

A ``request_id`` is carried in a context variable and injected into every log
record, so all logs for one HTTP/WS request can be correlated. Set/read it via
:func:`set_request_id` / :func:`get_request_id`.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

# Correlation id for the current request (empty outside a request).
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str:
    return _request_id.get()


class _RequestIdFilter(logging.Filter):
    """Attach the current request id to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class _JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Include any structured extras passed via logger.*(..., extra={...}).
        for key, value in record.__dict__.items():
            if key.startswith("ctx_"):
                payload[key[4:]] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure the root logger. Idempotent (safe to call once at startup)."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Remove pre-existing handlers so repeated calls don't duplicate output.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # On Windows the console defaults to cp1252, which crashes when a record
    # contains non-Latin-1 characters (e.g. Piper's IPA phonemes). Force UTF-8
    # and never raise on an unencodable char.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (ValueError, OSError):
                pass

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())

    if json_output:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | rid=%(request_id)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root.addHandler(handler)

    # Tame noisy third-party loggers; let ours flow at the configured level.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # Piper logs every sentence's phonemes at DEBUG — noisy and non-Latin-1.
    logging.getLogger("piper").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (use module __name__)."""
    return logging.getLogger(name)
