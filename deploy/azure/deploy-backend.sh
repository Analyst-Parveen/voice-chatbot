#!/usr/bin/env bash
# Update-deploy the BACKEND only (no Docker). Run on the VM after a git push:
#   cd /opt/voice-agent && bash deploy/azure/deploy-backend.sh [--ingest]
#
# --ingest also re-runs knowledge ingestion (needed when data/ docs changed).
# Ingestion requires the backend stopped (embedded Qdrant holds a file lock).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/voice-agent}"
BRANCH="${DEPLOY_BRANCH:-main}"
cd "$APP_DIR"

echo "==> Pulling latest ($BRANCH)…"
git fetch --all --prune
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

cd backend
echo "==> Updating Python dependencies…"
./venv/bin/pip install -q -e ".[voice,embeddings,ingest,cache]"

echo "==> Applying DB migrations…"
./venv/bin/alembic upgrade head

if [ "${1:-}" = "--ingest" ]; then
  echo "==> Re-ingesting knowledge docs (backend stopped for Qdrant lock)…"
  sudo systemctl stop voiceai-backend
  ./venv/bin/python -m ingestion.run_ingestion --data-dir ../data
fi

echo "==> Restarting backend…"
sudo systemctl restart voiceai-backend

echo "==> Waiting for health…"
for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "==> Backend healthy."
    exit 0
  fi
  sleep 5
done
echo "!! Backend not healthy yet — check: sudo journalctl -u voiceai-backend -n 50" >&2
exit 1
