#!/usr/bin/env bash
# Update-deploy the FRONTEND only (no Docker). Run on the VM after a git push:
#   cd /opt/voice-agent && bash deploy/azure/deploy-frontend.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/voice-agent}"
BRANCH="${DEPLOY_BRANCH:-main}"
cd "$APP_DIR"

echo "==> Pulling latest ($BRANCH)…"
git fetch --all --prune
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

cd frontend
echo "==> Installing packages + building…"
npm ci
export NEXT_PUBLIC_API_BASE_URL="$(grep -E '^NEXT_PUBLIC_API_BASE_URL=' ../.env | cut -d= -f2-)"
export NEXT_PUBLIC_WS_BASE_URL="$(grep -E '^NEXT_PUBLIC_WS_BASE_URL=' ../.env | cut -d= -f2-)"
npm run build

echo "==> Restarting frontend…"
sudo systemctl restart voiceai-frontend
sleep 3
sudo systemctl --no-pager status voiceai-frontend | head -5
echo "==> Frontend deployed."
