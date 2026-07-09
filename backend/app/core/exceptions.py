"""Application exception hierarchy and FastAPI handlers.

All errors return a consistent JSON envelope so the frontend can rely on one
shape:

    {"error": {"code": "not_found", "message": "...", "details": {...},
               "request_id": "..."}}

Raise the typed exceptions below from anywhere in the service/API layers; the
registered handlers turn them into proper HTTP responses. Unhandled errors are
caught by a catch-all handler and returned as a 500 without leaking internals.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, get_request_id
from app.core.metrics import app_errors_total

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all application errors.

    Attributes:
        status_code: HTTP status to return.
        code: stable machine-readable error code (snake_case).
        message: human-readable message safe to expose to clients.
        details: optional structured context.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.__class__.__doc__ or "Error"
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        super().__init__(self.message)


class NotFoundError(AppError):
    """Requested resource was not found."""

    status_code = 404
    code = "not_found"


class ValidationAppError(AppError):
    """Input failed validation."""

    status_code = 422
    code = "validation_error"


class UnauthorizedError(AppError):
    """Authentication is required or the credentials are invalid."""

    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    """Authenticated but not allowed to perform this action."""

    status_code = 403
    code = "forbidden"


class RateLimitError(AppError):
    """Too many requests."""

    status_code = 429
    code = "rate_limited"


class ServiceUnavailableError(AppError):
    """A downstream dependency (DB, Qdrant, Ollama, model) is unavailable."""

    status_code = 503
    code = "service_unavailable"


def _envelope(code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": get_request_id(),
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the app."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        app_errors_total.labels(code=exc.code).inc()
        if exc.status_code >= 500:
            logger.error("AppError: %s", exc.message, exc_info=exc)
        else:
            logger.info("AppError %s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        app_errors_total.labels(code="validation_error").inc()
        return JSONResponse(
            status_code=422,
            content=_envelope("validation_error", "Request validation failed",
                              {"errors": exc.errors()}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail), {}),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        app_errors_total.labels(code="internal_error").inc()
        logger.exception("Unhandled exception")
        # Never leak internal details to the client.
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "An unexpected error occurred", {}),
        )
