<!-- https://indcool.in/ -->

# Voice AI Assistant (Self-Hosted, 100% Free)

A standalone, enterprise-grade **Voice + Text AI Assistant** that answers strictly
from your company's own knowledge (RAG), stores conversations in your existing
**Microsoft SQL Server**, and embeds into your website as a floating widget.

Everything runs locally / self-hosted — **no paid APIs**. The only cost is your server.

> See [`docs/BUILD_VOICE_AGENT.md`](docs/BUILD_VOICE_AGENT.md) for the full plan,
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design, and
> [`backend/deploy/README.md`](backend/deploy/README.md) for deployment.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js · React · TypeScript · Tailwind · React Query |
| Backend | FastAPI · Pydantic v2 · async · WebSocket |
| LLM | Qwen2.5-Instruct via Ollama |
| STT / TTS | faster-whisper / Piper |
| Embeddings / Rerank | BAAI bge-m3 / bge-reranker-v2-m3 |
| Vector DB | Qdrant (embedded) |
| Database | Microsoft SQL Server or SQLite |
| Deploy | Native Ubuntu VM + systemd + nginx |

---

## Run modes

Backend mode is selected via `backend/.env` (never commit the runtime `.env` file).

| Mode | Template | Where |
|---|---|---|
| `stub` | `backend/.env.stub` | low-config PC, no AI |
| `local-light` | `backend/.env.local` | dev PC, tiny models |
| production | `backend/.env.azure` | Azure VM, full models |

Frontend URLs live in `frontend/.env.local` (dev) or `frontend/.env.production` (build).

---

## Quick start (local)

Requires **Python 3.11+** and **Node 18+**.

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.stub .env          # or .env.local for real AI
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
# frontend/.env.local is pre-filled for localhost
npm run dev
```

Open http://localhost:3000

---

## Quick start (server)

```bash
cp backend/.env.azure backend/.env && nano backend/.env
nano frontend/.env.production
bash backend/deploy/azure/backend-setup.sh
bash backend/deploy/azure/frontend-setup.sh
```

Full runbook: [`backend/deploy/azure/README.md`](backend/deploy/azure/README.md)

---

## Handy commands

```bash
make mode-stub       # backend/.env.stub -> backend/.env
make backend-dev
make frontend-dev
```

---

## Project layout

```
voice-ai-assistant/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── .env.local              # Local dev URLs
│   ├── .env.production         # Production URLs (build)
│   └── .env.example
├── backend/
│   ├── app/
│   ├── deploy/
│   ├── requirements.txt
│   ├── .env                    # Runtime (gitignored)
│   ├── .env.local              # Local dev template
│   ├── .env.azure              # Server template
│   └── .env.example
├── docs/
├── scripts/
├── data/                       # Company docs to ingest (gitignored)
├── models/                     # Downloaded AI models (gitignored)
└── README.md
```

---

## License / cost

All dependencies are free and open source. You pay only for the server that hosts it.
