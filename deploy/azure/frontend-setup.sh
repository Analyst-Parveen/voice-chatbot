#!/usr/bin/env bash
# One-time FRONTEND setup on the Azure VM — NO DOCKER.
# Installs Node 20, builds the Next.js app with the public URLs from .env,
# and installs a systemd service.
#
#   cd /opt/voice-agent && bash deploy/azure/frontend-setup.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/voice-agent}"
cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "!! $APP_DIR/.env missing — run: cp .env.azure .env  (then edit it)" >&2
  exit 1
fi

echo "==> [1/4] Node.js 20…"
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -c2-3)" -lt 18 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "==> [2/4] Install packages + build (public URLs come from .env)…"
cd frontend
npm ci
# Next.js bakes NEXT_PUBLIC_* in at BUILD time — export them from the root .env.
export NEXT_PUBLIC_API_BASE_URL="$(grep -E '^NEXT_PUBLIC_API_BASE_URL=' ../.env | cut -d= -f2-)"
export NEXT_PUBLIC_WS_BASE_URL="$(grep -E '^NEXT_PUBLIC_WS_BASE_URL=' ../.env | cut -d= -f2-)"
npm run build

echo "==> [3/4] systemd service…"
cd "$APP_DIR"
sudo cp deploy/azure/voiceai-frontend.service /etc/systemd/system/
sudo sed -i "s|__APP_DIR__|$APP_DIR|g" /etc/systemd/system/voiceai-frontend.service
sudo systemctl daemon-reload
sudo systemctl enable --now voiceai-frontend

echo "==> [4/4] nginx edge (routes /api + /ws → backend, rest → frontend)…"
sudo cp deploy/azure/nginx-voiceai.conf /etc/nginx/sites-available/voiceai
sudo ln -sf /etc/nginx/sites-available/voiceai /etc/nginx/sites-enabled/voiceai
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "==> Frontend setup complete. Open http://<VM_IP> in a browser."
