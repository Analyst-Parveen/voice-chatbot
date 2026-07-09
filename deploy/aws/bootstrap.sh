#!/usr/bin/env bash
# One-time provisioning for a FRESH Ubuntu 22.04/24.04 EC2 instance.
# Installs Docker + Compose, clones the repo, and prepares .env.
#
#   Usage on the server (as a sudo-capable user):
#     curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy/aws/bootstrap.sh | bash -s -- <git-repo-url>
#   or copy this file up and run:  bash bootstrap.sh <git-repo-url>
set -euo pipefail

REPO_URL="${1:-}"
APP_DIR="${APP_DIR:-/opt/voice-agent}"
BRANCH="${DEPLOY_BRANCH:-main}"

if [ -z "$REPO_URL" ]; then
  echo "Usage: bash bootstrap.sh <git-repo-url>" >&2
  exit 1
fi

echo "==> Installing Docker Engine + Compose plugin…"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl git
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER" || true
fi

echo "==> Cloning repo to $APP_DIR…"
sudo mkdir -p "$APP_DIR"
sudo chown "$USER":"$USER" "$APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

if [ ! -f .env ]; then
  cp .env.docker .env
  echo ""
  echo "!! Created $APP_DIR/.env from the template."
  echo "!! EDIT IT NOW and set: MSSQL_* creds, JWT_SECRET, CORS_ORIGINS,"
  echo "!! NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_WS_BASE_URL."
fi

echo ""
echo "==> Bootstrap done."
echo "    1) Edit $APP_DIR/.env with real values."
echo "    2) Put your knowledge docs in $APP_DIR/data/"
echo "    3) First deploy:   cd $APP_DIR && bash deploy/aws/deploy.sh"
echo "    4) Ingest docs:    docker compose exec backend python -m ingestion.run_ingestion --data-dir /app/data"
echo "    (You may need to log out/in once for docker group membership to apply.)"
