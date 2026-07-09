"""Security helpers: CORS config and an auth-ready authentication seam.

Auth is intentionally a *seam* in these early phases: with ``AUTH_ENABLED=false``
(the default) every request is treated as anonymous, so the app is fully usable
standalone. When the assistant is embedded into the company website
(Phase 10), flip ``AUTH_ENABLED=true`` and replace :func:`verify_token` with a
real verifier that validates the site's JWT and maps it to ``user_ref`` — no
other code changes required, because everything depends on :class:`AuthContext`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError


def build_cors_kwargs(settings: Settings) -> dict:
    """CORS middleware kwargs derived from settings (allowlist from env)."""
    origins = list(settings.cors_origins)
    if settings.app_env == "development":
        # Next.js may bind to 3001, 3002, … when 3000 is taken.
        for port in range(3000, 3010):
            origin = f"http://localhost:{port}"
            if origin not in origins:
                origins.append(origin)
        for port in range(3000, 3010):
            origin = f"http://127.0.0.1:{port}"
            if origin not in origins:
                origins.append(origin)
    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


@dataclass
class AuthContext:
    """Who is making the request. ``user_ref`` links to the existing website
    user once real auth is wired; anonymous sessions are allowed."""

    user_ref: str | None = None
    is_authenticated: bool = False
    roles: list[str] = field(default_factory=list)

    @property
    def is_anonymous(self) -> bool:
        return not self.is_authenticated


def _extract_bearer(authorization: str | None) -> str | None:
    """Pull the token out of an ``Authorization: Bearer <token>`` header."""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def verify_token(token: str, settings: Settings) -> AuthContext:
    """Verify a bearer token and return the caller's context.

    Placeholder verifier for the auth seam. It only checks that a non-empty
    token was supplied and derives an opaque ``user_ref`` from it. Phase 10
    replaces the body with real JWT validation (signature + claims) using
    ``settings.jwt_secret``; the return type stays the same.
    """
    if not token:
        raise UnauthorizedError("Missing bearer token")
    # NOTE: not cryptographically verified yet — replaced in Phase 10.
    return AuthContext(user_ref=f"token:{token[:12]}", is_authenticated=True)


def resolve_auth(authorization: str | None, settings: Settings) -> AuthContext:
    """Resolve an :class:`AuthContext` for a request.

    - Auth disabled  → anonymous context (standalone mode).
    - Auth enabled    → require and verify a bearer token.
    """
    if not settings.auth_enabled:
        return AuthContext()  # anonymous, allowed
    token = _extract_bearer(authorization)
    if not token:
        raise UnauthorizedError("Authorization header with bearer token required")
    return verify_token(token, settings)
