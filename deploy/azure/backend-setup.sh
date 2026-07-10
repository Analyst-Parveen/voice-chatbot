#!/usr/bin/env bash
# One-time BACKEND setup on a fresh Ubuntu 22.04/24.04 Azure VM — NO DOCKER.
# Installs natively: Python 3.11 venv + deps, Ollama (+ LLM), Redis, Piper
# voices, DB migrations, and a systemd service for the API.
#
#   cd /opt/voice-agent && bash deploy/azure/backend-setup.sh
#
# Prereqs: repo cloned to $APP_DIR and .env created (cp .env.azure .env; edit).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/voice-agent}"
cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "!! $APP_DIR/.env missing — run: cp .env.azure .env  (then edit it)" >&2
  exit 1
fi

echo "==> [1/7] System packages (Python 3.11, ffmpeg, nginx, redis)…"
sudo apt-get update -y
sudo apt-get install -y software-properties-common curl git ffmpeg nginx redis-server
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -y
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
sudo systemctl enable --now redis-server

echo "==> [2/7] Ollama (native) + LLM model…"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable --now ollama || true
LLM_MODEL="$(grep -E '^LLM_MODEL=' .env | cut -d= -f2 | tr -d ' ')"
ollama pull "${LLM_MODEL:-qwen2.5:3b}"

echo "==> [3/7] Python venv + backend dependencies (heavy — one time)…"
cd backend
if [ ! -d venv ]; then python3.11 -m venv venv; fi
./venv/bin/pip install --upgrade pip
# Same tools as the Docker image: voice (whisper+piper), embeddings (bge-m3 +
# reranker), ingest (doc loaders), cache (redis). Add ,mssql after installing
# the Microsoft ODBC driver if you use SQL Server.
./venv/bin/pip install -e ".[voice,embeddings,ingest,cache]"

echo "==> [4/7] Piper voices…"
./venv/bin/python scripts/download_models.py --piper || echo "(piper download skipped)"

echo "==> [5/7] Database migrations…"
./venv/bin/alembic upgrade head

echo "==> [6/7] Knowledge ingestion (backend must be stopped — embedded Qdrant)…"
sudo systemctl stop voiceai-backend 2>/dev/null || true
./venv/bin/python -m ingestion.run_ingestion --data-dir ../data || \
  echo "(ingestion failed/skipped — put docs in $APP_DIR/data and re-run deploy-backend.sh --ingest)"

echo "==> [7/7] systemd service…"
cd "$APP_DIR"
sudo cp deploy/azure/voiceai-backend.service /etc/systemd/system/
sudo sed -i "s|__APP_DIR__|$APP_DIR|g" /etc/systemd/system/voiceai-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now voiceai-backend

echo ""
echo "==> Backend setup complete. Check:  sudo systemctl status voiceai-backend"
echo "    (first start is slow: it warms Whisper + bge-m3 into cache)"
