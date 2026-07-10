#!/usr/bin/env bash
# One-time FRONTEND setup on the Azure VM — NO DOCKER.
#
#   cd /opt/voice-agent && bash backend/deploy/azure/frontend-setup.sh
#
# Prereqs: edit frontend/.env.production with your public API/WS URLs
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/voice-agent}"
cd "$APP_DIR"

if [ ! -f frontend/.env.production ]; then
  echo "!! $APP_DIR/frontend/.env.production missing — copy from frontend/.env.example" >&2
  exit 1
fi

echo "==> [1/4] Node.js 20…"
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -c2-3)" -lt 18 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "==> [2/4] Install packages + build (URLs from frontend/.env.production)…"
cd frontend
npm ci
export NEXT_PUBLIC_API_BASE_URL="$(grep -E '^NEXT_PUBLIC_API_BASE_URL=' .env.production | cut -d= -f2-)"
export NEXT_PUBLIC_WS_BASE_URL="$(grep -E '^NEXT_PUBLIC_WS_BASE_URL=' .env.production | cut -d= -f2-)"
npm run build

echo "==> [3/4] systemd service…"
cd "$APP_DIR"
sudo cp backend/deploy/azure/voiceai-frontend.service /etc/systemd/system/
sudo sed -i "s|__APP_DIR__|$APP_DIR|g" /etc/systemd/system/voiceai-frontend.service
sudo systemctl daemon-reload
sudo systemctl enable --now voiceai-frontend

echo "==> [4/4] nginx edge…"
sudo cp backend/deploy/azure/nginx-voiceai.conf /etc/nginx/sites-available/voiceai
sudo ln -sf /etc/nginx/sites-available/voiceai /etc/nginx/sites-enabled/voiceai
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "==> Frontend setup complete. Open http://<VM_IP> in a browser."
