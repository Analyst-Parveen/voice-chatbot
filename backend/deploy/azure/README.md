# Azure VM deployment — NO Docker (native installs)

Runs the exact same stack as the Docker profile — **same tools, same models,
same accuracy** — installed natively on one Ubuntu VM and managed by systemd:

| Piece | How it runs (no Docker) |
|---|---|
| Backend (FastAPI) | Python 3.11 venv → `voiceai-backend` systemd service on :8000 |
| Frontend (Next.js) | Node 20 build → `voiceai-frontend` systemd service on :3000 |
| Ollama + qwen2.5:3b | Native Ollama service (installer creates it) on :11434 |
| Qdrant | **Embedded mode** — library inside the backend, data in `backend/qdrant_local/`. No server to install. Same engine & accuracy. |
| Redis | Native `redis-server` on :6379 (cache, rate-limit, helpdesk state) |
| Whisper small / bge-m3 / reranker / Piper | Auto-download into the backend on first start |
| nginx | Native, routes `/api` + `/ws` → backend, rest → frontend |
| Database | SQLite file by default; switch `.env` to your SQL Server when ready |

Backend and frontend are **independent**: each has its own setup script,
deploy script, and service — you can update one without touching the other.

---

## 1. Create the VM (Azure portal)

- **Image:** Ubuntu Server 24.04 LTS (or 22.04)
- **Size:** `Standard_F8s_v2` (8 vCPU / 16 GB) — CPU-only is fine
- **Disk:** 64 GB+
- **NSG inbound:** allow `22`, `80`, `443`

## 2. One-time setup (on the VM)

```bash
ssh azureuser@<VM_IP>

# get the code (private repo → use a GitHub token with `repo` scope)
sudo mkdir -p /opt/voice-agent && sudo chown $USER:$USER /opt/voice-agent
git clone https://<TOKEN>@github.com/infinitymasters2023/voice-ai-assistant.git /opt/voice-agent
cd /opt/voice-agent

# config
cp backend/.env.azure backend/.env
nano backend/.env      # CORS_ORIGINS, JWT_SECRET, DB creds
nano frontend/.env.production   # NEXT_PUBLIC_* URLs

# company documents
#   copy your docs into /opt/voice-agent/data/   (scp / rsync)

bash backend/deploy/azure/backend-setup.sh
bash backend/deploy/azure/frontend-setup.sh
```

Open `http://<VM_IP>` — the widget is live.

## 3. Updates after a `git push`

```bash
cd /opt/voice-agent
bash backend/deploy/azure/deploy-backend.sh            # backend only
bash backend/deploy/azure/deploy-frontend.sh           # frontend only
bash backend/deploy/azure/deploy-backend.sh --ingest   # backend + re-ingest docs
```

## 4. Operations

```bash
sudo systemctl status voiceai-backend voiceai-frontend
sudo journalctl -u voiceai-backend -f          # live backend logs
sudo systemctl restart voiceai-backend         # restart
```

## 5. TLS / HTTPS

Point a domain at the VM, then:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx
```

Update `frontend/.env.production` `NEXT_PUBLIC_*` to `https://` / `wss://` and re-run
`backend/deploy/azure/deploy-frontend.sh` (URLs are baked in at build time).

---

## Rules that keep it healthy (embedded Qdrant)

1. **Exactly ONE backend process.** The systemd unit runs a single worker —
   never start a second uvicorn by hand, never use `--reload`.
2. **Stop the backend before ingestion.** `deploy-backend.sh --ingest` does
   this for you.
3. First backend start after boot is slow (model warm-up) — the service
   allows up to 10 minutes; watch it with `journalctl -u voiceai-backend -f`.

## SQL Server note

To use the company MSSQL instead of SQLite: install the Microsoft ODBC driver
(`msodbcsql17`), run `./venv/bin/pip install -e ".[mssql]"`, flip the
`DB_BACKEND=mssql` block in `backend/.env`, then `deploy-backend.sh`.
