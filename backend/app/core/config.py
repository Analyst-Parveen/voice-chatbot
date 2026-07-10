"""Application configuration.

All settings are loaded from environment variables (or a local `.env` file)
via Pydantic Settings. Nothing is hardcoded; secrets never live in code.

The central switch is ``RUN_MODE`` which selects how the app behaves on a
low-config PC vs. a server — see ``RunMode`` below. Application code stays
identical across modes; only the values here change.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repo root is three levels up from this file (core -> app -> backend -> root).
# We load the shared root `.env` no matter what directory the process starts
# in (backend/, repo root, or Docker), and let a local backend/.env override.
_REPO_ROOT = Path(__file__).resolve().parents[3]


class RunMode(str, Enum):
    """How the assistant runs. Selected by the ``RUN_MODE`` env var."""

    STUB = "stub"                # fake AI, no models, no Docker (weak PC)
    LOCAL_LIGHT = "local-light"  # tiny real models, no Docker (weak PC)
    DOCKER_FULL = "docker-full"  # full models on the server via Docker


class DBBackend(str, Enum):
    """Which database engine to use."""

    SQLITE = "sqlite"  # lightweight local dev fallback only
    MSSQL = "mssql"    # production: existing Microsoft SQL Server


class Settings(BaseSettings):
    """Typed application settings, populated from the environment."""

    model_config = SettingsConfigDict(
        # Later files win, so backend/.env (cwd) overrides the shared root .env.
        env_file=(str(_REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Run mode ----
    run_mode: RunMode = Field(default=RunMode.STUB, alias="RUN_MODE")

    # ---- App ----
    app_name: str = Field(default="voice-ai-assistant", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")

    # ---- Server ----
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")

    # ---- CORS (comma-separated string in env -> list) ----
    # NoDecode: don't let pydantic-settings JSON-parse this; the validator
    # below splits the comma-separated env string into a list.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"], alias="CORS_ORIGINS"
    )

    # ---- Database ----
    db_backend: DBBackend = Field(default=DBBackend.SQLITE, alias="DB_BACKEND")
    sqlite_path: str = Field(default="./voiceai_dev.sqlite3", alias="SQLITE_PATH")
    mssql_host: str = Field(default="localhost", alias="MSSQL_HOST")
    mssql_port: int = Field(default=1433, alias="MSSQL_PORT")
    mssql_db: str = Field(default="IAPL", alias="MSSQL_DB")
    mssql_user: str = Field(default="sa", alias="MSSQL_USER")
    mssql_password: str = Field(default="", alias="MSSQL_PASSWORD")
    mssql_driver: str = Field(default="ODBC Driver 17 for SQL Server", alias="MSSQL_DRIVER")
    db_schema: str = Field(default="voiceai", alias="DB_SCHEMA")

    # ---- Ollama (LLM) ----
    ollama_url: str = Field(default="http://localhost:11434", alias="OLLAMA_URL")
    llm_model: str = Field(default="qwen2.5:0.5b", alias="LLM_MODEL")
    # Max seconds to wait for Ollama (slow CPUs may need several minutes per turn).
    ollama_timeout_seconds: float = Field(default=600.0, alias="OLLAMA_TIMEOUT_SECONDS")

    # ---- Qdrant (vector DB) ----
    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_path: str = Field(default="./qdrant_local", alias="QDRANT_PATH")
    qdrant_collection: str = Field(default="company_knowledge", alias="QDRANT_COLLECTION")

    # ---- Redis (optional cache + shared state) ----
    # Empty = disabled: rate limiting and helpdesk state stay in-process and no
    # answer caching happens (identical to the low-config local behavior). Set to
    # e.g. redis://redis:6379/0 on the server to enable all three.
    redis_url: str = Field(default="", alias="REDIS_URL")
    cache_ttl_seconds: int = Field(default=3600, alias="CACHE_TTL_SECONDS")

    # ---- Models ----
    whisper_model: str = Field(default="small", alias="WHISPER_MODEL")
    whisper_device: str = Field(default="cpu", alias="WHISPER_DEVICE")  # cpu | cuda
    embed_model: str = Field(default="BAAI/bge-m3", alias="EMBED_MODEL")
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANKER_MODEL")
    piper_voice: str = Field(default="hi_IN-priyamvada-medium", alias="PIPER_VOICE")

    # ---- RAG tuning ----
    rag_enabled: bool = Field(default=False, alias="RAG_ENABLED")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    rag_score_threshold: float = Field(default=0.35, alias="RAG_SCORE_THRESHOLD")
    rag_use_reranker: bool = Field(default=True, alias="RAG_USE_RERANKER")
    rag_min_context_chars: int = Field(default=40, alias="RAG_MIN_CONTEXT_CHARS")

    # ---- Security ----
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    jwt_secret: str = Field(default="change_me", alias="JWT_SECRET")

    # ---- Helpdesk external integration (optional) ----
    helpdesk_api_url: str = Field(default="", alias="HELPDESK_API_URL")

    # ---- Validators ----
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        """Allow CORS_ORIGINS to be a comma-separated string in the env file."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # ---- Convenience helpers ----
    @property
    def is_stub(self) -> bool:
        return self.run_mode is RunMode.STUB

    @property
    def is_docker(self) -> bool:
        return self.run_mode is RunMode.DOCKER_FULL

    @property
    def use_sqlite(self) -> bool:
        return self.db_backend is DBBackend.SQLITE


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single source of truth)."""
    return Settings()
