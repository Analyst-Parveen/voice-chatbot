<!-- https://indcool.in/ -->

# Voice AI Assistant (Self-Hosted, 100% Free)

A standalone, enterprise-grade **Voice + Text AI Assistant** that answers strictly
from your company's own knowledge (RAG), stores conversations in your existing
**Microsoft SQL Server**, and later embeds into your website as a floating widget.

Everything runs locally / self-hosted — **no paid APIs** (no OpenAI, Claude,
Gemini, ElevenLabs, Deepgram, Azure, or AWS AI). The only cost is your server.

> Build progress: **All 10 phases complete** ✅ — scaffold, config, database,
> backend core, frontend widget, RAG, Voice, Deployment, Testing & Monitoring,
> and Website Integration (embeddable `widget.js` with a one-snippet embed).
> See [`BUILD_VOICE_AGENT.md`](BUILD_VOICE_AGENT.md) for the full plan,
> [`ARCHITECTURE.md`](ARCHITECTURE.md) for the design, and
> [`deploy/README.md`](deploy/README.md) for deployment + website embedding.

---











## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js · React · TypeScript · Tailwind · React Query |
| Backend | FastAPI · Pydantic v2 · async · WebSocket |
| LLM | Qwen2.5-Instruct via Ollama |
| STT / TTS | faster-whisper / Piper |
| Embeddings / Rerank | BAAI bge-m3 / bge-reranker-v2-m3 |
| Vector DB | Qdrant |
| Database | Microsoft SQL Server (existing) via SQLAlchemy + Alembic |
| Deploy | Docker Compose |

---

## Run modes

Pick a mode with a single env file. Switching modes changes **only `.env`** — never code.

| Mode | Where | Models |
|---|---|---|
| `stub` | low-config PC | fake responses |
| `local-light` (via `.env.local`) | low-config PC | tiny (Qwen 0.5B, Whisper base) |
| `local-light` (via `.env.azure`) | server VM | full (Qwen 3B, Whisper small, reranker) |

**Golden path on a weak PC:** `stub` (build & verify everything) → tiny models
(sanity-check real AI) → server VM with `.env.azure` (full models, live).

---

## Quick start (local, no Docker)

Requires **Python 3.11+** and **Node 18+**.

### 1. Backend (terminal 1)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Git Bash / macOS / Linux:  source .venv/bin/activate
pip install -e ".[dev]"

cp ../.env.stub ../.env          # start in stub mode (no AI, no SQL Server)
uvicorn app.main:app --reload --port 8000
```

Check it: open http://localhost:8000/api/health → `{"status":"ok",...}`
API docs: http://localhost:8000/docs

### 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — the skeleton page shows the backend health status.

---

## Quick start (server — no Docker)

Deploys natively to one Ubuntu VM (Azure/AWS), managed by systemd:

```bash
cp .env.azure .env                    # then edit: public URLs, JWT, DB creds
bash deploy/azure/backend-setup.sh    # Python, Ollama+model, Redis, service
bash deploy/azure/frontend-setup.sh   # Node, build, service, nginx
```

Full runbook: [`deploy/azure/README.md`](deploy/azure/README.md)

---

## Handy commands

```bash
make mode-stub      # copy .env.stub -> .env
make backend-dev    # run FastAPI (autoreload)
make frontend-dev   # run Next.js
```

---

## Project layout

```
voice-agent/
├── backend/     FastAPI app, services, RAG, ingestion, DB (SQLAlchemy)
├── frontend/    Next.js app + embeddable chat widget
├── deploy/      nginx + deployment / website-embed guide
├── models/      downloaded model files (gitignored)
└── data/        source docs to ingest (gitignored)
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full breakdown.

---

## License / cost

All dependencies are free and open source. You pay only for the server that hosts it.
