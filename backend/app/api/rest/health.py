"""Health check endpoints.

- ``/api/health``  full snapshot: liveness, run mode, and per-dependency status.
- ``/api/health/live``   liveness only (fast; for container/orchestrator probes).
- ``/api/health/ready``  readiness: 200 only when no dependency is unreachable.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app import __version__
from app.api.deps import SettingsDep
from app.core.health import check_dependencies, overall_status
from app.db.session import ping_database

router = APIRouter(tags=["health"])


async def _dependency_snapshot(settings: SettingsDep) -> dict[str, str]:
    """Assemble live dependency statuses, including a real DB ping."""
    dependencies = check_dependencies(settings)
    dependencies["database"] = "ok" if await ping_database() else "unreachable"
    return dependencies


class HealthResponse(BaseModel):
    """Response schema for the health endpoint."""

    status: str
    version: str
    run_mode: str
    app_env: str
    db_backend: str
    dependencies: dict[str, str]


@router.get("/health", response_model=HealthResponse, summary="Liveness & dependency status")
async def health(settings: SettingsDep) -> HealthResponse:
    """Return service liveness plus a live snapshot of each dependency."""
    dependencies = await _dependency_snapshot(settings)
    return HealthResponse(
        status=overall_status(dependencies),
        version=__version__,
        run_mode=settings.run_mode.value,
        app_env=settings.app_env,
        db_backend=settings.db_backend.value,
        dependencies=dependencies,
    )


@router.get("/health/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    """Cheap liveness check — the process is up and serving."""
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def ready(settings: SettingsDep, response: Response) -> dict[str, object]:
    """Readiness — 503 if any dependency is unreachable."""
    dependencies = await _dependency_snapshot(settings)
    status = overall_status(dependencies)
    if status != "ok":
        response.status_code = 503
    return {"status": status, "dependencies": dependencies}
