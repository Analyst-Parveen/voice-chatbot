#!/bin/sh
# Backend container entrypoint.
# 1) download the Piper voice (idempotent), 2) apply DB migrations,
# 3) start the API server. Steps 1–2 are best-effort so a transient DB/network
# hiccup doesn't wedge the container — errors are logged and the app still boots
# (its /api/health readiness will report any unmet dependency).
set -e

echo "[entrypoint] downloading Piper voice (if missing)…"
python scripts/download_models.py --piper || echo "[entrypoint] piper download skipped/failed"

echo "[entrypoint] applying database migrations…"
alembic upgrade head || echo "[entrypoint] migration failed — is SQL Server reachable? Continuing."

echo "[entrypoint] starting API on port ${BACKEND_PORT:-8000}…"
exec uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8000}"
