# Windows VM deployment — NO Docker, NO Linux

Runs the real stack (same models, same accuracy as any server) natively on a
**Windows Server / Windows VM**. Same setup you use locally — nothing changes.

| Piece | How it runs (Windows, no Docker) |
|---|---|
| Backend (FastAPI) | Python venv → `uvicorn` on :8000, auto-starts via the `voiceai-backend` Scheduled Task |
| Frontend (Next.js) | Node build → `npm start` on :3000 |
| Ollama + qwen2.5:3b | Native Ollama (Windows installer) on :11434 |
| Qdrant | **Embedded** — a library inside the backend, data in `backend\qdrant_local\`. No server to install. |
| Whisper small / bge-m3 / reranker / Piper | Downloaded by `backend-setup.ps1` and on first use |
| Database | SQLite file by default; switch `.env` to your SQL Server when ready |

---

## The 5 steps to get it running on a VM

### 1. Get the project onto the VM
Copy the whole `voice-ai-assistant` folder to the VM (e.g. `D:\voice-ai-assistant`),
or `git clone` it. If you clone, you must create the two env files in step 2
(they are gitignored and never travel with git).

### 2. Set the env files (both)

**`backend\.env`** — the real-models config:
```
RUN_MODE=local-light
DB_BACKEND=sqlite
SQLITE_PATH=./voiceai_dev.sqlite3
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:3000          # add your VM URL for remote access
OLLAMA_URL=http://localhost:11434
LLM_MODEL=qwen2.5:3b
WHISPER_MODEL=small
PIPER_VOICE=hi_IN-priyamvada-medium
EMBED_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
QDRANT_PATH=./qdrant_local
QDRANT_COLLECTION=company_knowledge
RAG_ENABLED=true
RAG_USE_RERANKER=true
JWT_SECRET=change_me_to_a_long_random_string
```

**`frontend\.env.local`** — the URLs the widget calls:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```
For remote access, replace `localhost` with the VM's IP or domain (and use
`https://` / `wss://` once you put TLS in front).

### 3. Install backend Python dependencies
```powershell
cd D:\voice-ai-assistant\backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```
> `backend-setup.ps1` also does this, so this step is optional — but it matches
> the manual flow if you prefer to install deps yourself first.

### 4. Run the backend setup
```powershell
cd D:\voice-ai-assistant
powershell -ExecutionPolicy Bypass -File backend\deploy\azure\backend-setup.ps1
```
This installs tools (Python/Git/ffmpeg/Ollama), pulls `qwen2.5:3b`, sets up the
venv, **downloads the Piper voices + Whisper + embedding model**, runs DB
migrations, ingests any docs in `data\`, and registers the `voiceai-backend`
Scheduled Task so the backend auto-starts on boot.

Optionally set up the frontend the same way:
```powershell
powershell -ExecutionPolicy Bypass -File backend\deploy\azure\frontend-setup.ps1
```

### 5. Run frontend + backend

**Backend** (if the Scheduled Task from step 4 isn't already running it):
```powershell
powershell -File backend\deploy\azure\start-backend.ps1
```

**Frontend:**
```powershell
# production build (after frontend-setup.ps1):
powershell -File backend\deploy\azure\start-frontend.ps1
# or, for development:
cd D:\voice-ai-assistant\frontend
npm run dev
```

Open **http://localhost:3000** (or `http://<VM_IP>:3000` from another machine).
Backend health: **http://localhost:8000/api/health**.

---

## Adding / refreshing company knowledge

```powershell
# 1. Stop the backend first (embedded Qdrant is single-writer)
Stop-ScheduledTask -TaskName voiceai-backend      # or Ctrl+C if run manually

# 2. Fetch pages -> data\ -> embed
cd D:\voice-ai-assistant
python scripts\fetch_and_ingest.py https://your-company.com --crawl

# 3. Start the backend again
Start-ScheduledTask -TaskName voiceai-backend
```

## Rules that keep it healthy (embedded Qdrant)

1. **Exactly ONE backend process.** Never start a second `uvicorn` by hand, and
   don't use `--reload` on the server.
2. **Stop the backend before ingesting** — the `qdrant_local` folder can only be
   opened by one process at a time.
3. **First start after boot is slow** (model warm-up loads qwen + reranker into
   RAM). That's normal — give it a couple of minutes.

## Scheduled Task commands (auto-start)

```powershell
Get-ScheduledTask   -TaskName voiceai-backend     # status
Start-ScheduledTask -TaskName voiceai-backend     # start now
Stop-ScheduledTask  -TaskName voiceai-backend     # stop
```

## Switching to SQL Server (optional)

To use the company MSSQL instead of SQLite: install the Microsoft ODBC driver
("ODBC Driver 17 for SQL Server"), then in `backend\.env` set:
```
DB_BACKEND=mssql
MSSQL_HOST=...
MSSQL_DB=IAPL
MSSQL_USER=...
MSSQL_PASSWORD=...
```
and restart the backend.
