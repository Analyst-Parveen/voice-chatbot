"""Unit tests for settings parsing."""

from app.core.config import DBBackend, RunMode, Settings


def test_cors_origins_split_from_csv() -> None:
    s = Settings(CORS_ORIGINS="http://a.com, http://b.com ,http://c.com")
    assert s.cors_origins == ["http://a.com", "http://b.com", "http://c.com"]


def test_cors_origins_accepts_list() -> None:
    s = Settings(CORS_ORIGINS=["http://a.com"])
    assert s.cors_origins == ["http://a.com"]


def test_run_mode_and_helpers() -> None:
    s = Settings(RUN_MODE="stub", DB_BACKEND="sqlite")
    assert s.run_mode is RunMode.STUB
    assert s.is_stub is True
    assert s.use_sqlite is True
    assert s.db_backend is DBBackend.SQLITE
