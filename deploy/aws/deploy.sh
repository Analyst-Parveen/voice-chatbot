#!/usr/bin/env bash
# Remote deploy step — run ON the EC2 host (by CI over SSH, or by hand).
#
# Pulls the latest code and (re)builds + restarts the whole stack. All backing
# services (Qdrant, Redis, Ollama, model downloads) are provisioned by Docker
# Compose itself, so this script only needs Docker + the repo.
#
# It intentionally does NOT touch .env — the server's .env (with real MSSQL
# creds / JWT secret) is created once by bootstrap.sh and preserved across
# deploys.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/voice-agent}"
BRANCH="${DEPLOY_BRANCH:-main}"

cd "$APP_DIR"

echo "==> Fetching latest ($BRANCH)…"
git fetch --all --prune
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

if [ ! -f .env ]; then
  echo "!! No .env found in $APP_DIR — copy .env.docker to .env and fill in secrets first." >&2
  exit 1
fi

echo "==> Building and starting the stack…"
docker compose up -d --build --remove-orphans

echo "==> Waiting for backend health…"
for i in $(seq 1 40); do
  if docker compose exec -T backend python -c \
      "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').status==200 else 1)" 2>/dev/null; then
    echo "==> Backend healthy."
    break
  fi
  sleep 5
done

echo "==> Pruning old images…"
docker image prune -f >/dev/null 2>&1 || true

echo "==> Deploy complete. Running containers:"
docker compose ps
