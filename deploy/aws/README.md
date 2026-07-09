# Deploying to AWS (EC2 + Docker Compose)

The whole stack is self-provisioning. On the server, Docker Compose starts and
wires everything together — **you do not install Qdrant, Redis, Ollama, or any
model by hand**:

| Service | Provisioned by | Notes |
|---|---|---|
| Qdrant (vector DB) | `qdrant` service + `qdrant_storage` volume | persists across restarts |
| Redis (cache / rate-limit / helpdesk state) | `redis` service + `redis_data` volume | enabled via `REDIS_URL` |
| Ollama + LLM | `ollama` + one-shot `ollama-init` (pulls `LLM_MODEL`) | model cached in `ollama_models` |
| Whisper + bge-m3 + reranker | backend **startup warm-up** → `hf_cache` volume | downloaded on first boot |
| Piper voices | backend entrypoint `download_models.py --piper` | Hindi + English |
| nginx edge (`:80`) | `nginx` service | routes `/api` + `/ws` → backend, rest → frontend |

Server config lives in **`.env`** (from `.env.docker`): heavy models
(`qwen2.5:3b`, `bge-m3`, reranker on), `RAG_ENABLED=true`, `AUTH_ENABLED=true`,
and `REDIS_URL=redis://redis:6379/0`.

---

## 1. Launch an EC2 instance

- **CPU-only:** `c7i.2xlarge` (8 vCPU / 16 GB) is a reasonable start.
- **GPU (faster replies):** `g4dn.xlarge` — also deploy with the GPU override
  (`docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`) and
  install the NVIDIA container toolkit.
- OS: Ubuntu 22.04/24.04. Root disk: **60 GB+** (models are large).
- Security group inbound: `80` (HTTP), `443` (HTTPS if you add TLS), `22` (SSH).

## 2. One-time bootstrap (on the instance)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy/aws/bootstrap.sh) <git-repo-url>
# then edit the generated /opt/voice-agent/.env with real values:
#   MSSQL_* creds, JWT_SECRET, CORS_ORIGINS,
#   NEXT_PUBLIC_API_BASE_URL / NEXT_PUBLIC_WS_BASE_URL (your public https/wss URLs)
```

Put your knowledge documents in `/opt/voice-agent/data/`.

## 3. First deploy + ingest

```bash
cd /opt/voice-agent
bash deploy/aws/deploy.sh
# populate the vector DB from your docs (run once, and after doc changes):
docker compose exec backend python -m ingestion.run_ingestion --data-dir /app/data
```

## 4. Continuous deploy from GitHub

Add these repo secrets (**Settings → Secrets and variables → Actions**):

| Secret | Value |
|---|---|
| `EC2_HOST` | instance public DNS/IP |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | the **private** PEM for the instance key pair |
| `APP_DIR` | *(optional)* defaults to `/opt/voice-agent` |

Every push to `main` runs [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml),
which SSHes in and runs `deploy/aws/deploy.sh` (git pull → `docker compose up -d
--build`). Your server `.env` is never overwritten.

## 5. TLS (recommended)

nginx terminates plain HTTP on `:80`. For production put HTTPS in front:

- **Easiest:** an AWS Application Load Balancer with an ACM certificate → forward
  `:443` to the instance `:80`. Then set `NEXT_PUBLIC_*` to `https://`/`wss://`.
- **On-box:** add Caddy or certbot + an nginx `:443` server block.

Once TLS is live, make sure `CORS_ORIGINS` and the `NEXT_PUBLIC_*` URLs all use
`https://` / `wss://`.

## Operations cheatsheet

```bash
docker compose ps                     # status
docker compose logs -f backend        # backend logs
docker compose restart backend        # restart one service
docker compose down                   # stop all (volumes/data preserved)
```

**Cost tip:** the instance is the bill, not Docker. If the assistant is only
needed during business hours, schedule instance stop/start (EventBridge +
Lambda, or `aws ec2 stop-instances` on a cron) to roughly halve the cost.
