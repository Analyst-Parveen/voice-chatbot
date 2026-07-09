"""Unit tests for the auth seam."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.core.security import resolve_auth


def _settings(**kw) -> Settings:
    base = {"DB_BACKEND": "sqlite"}
    base.update(kw)
    return Settings(**base)


def test_auth_disabled_is_anonymous() -> None:
    ctx = resolve_auth(None, _settings(AUTH_ENABLED=False))
    assert ctx.is_anonymous is True
    assert ctx.user_ref is None


def test_auth_enabled_requires_token() -> None:
    with pytest.raises(UnauthorizedError):
        resolve_auth(None, _settings(AUTH_ENABLED=True))


def test_auth_enabled_accepts_bearer() -> None:
    ctx = resolve_auth("Bearer abc123token", _settings(AUTH_ENABLED=True))
    assert ctx.is_authenticated is True
    assert ctx.user_ref is not None


def test_auth_enabled_rejects_malformed_header() -> None:
    with pytest.raises(UnauthorizedError):
        resolve_auth("NotBearer xyz", _settings(AUTH_ENABLED=True))
