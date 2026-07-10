# BUILD INSTRUCTIONS — Enterprise Voice AI Assistant (100% Free / Self-Hosted)

> **This file is a build command for Claude.**
> Give it to Claude Code and say: *"Read BUILD_VOICE_AGENT.md and build Phase N."*
> Build **one phase at a time**, in order. Do not skip phases. After each phase, stop, show what was built, and wait for approval before the next phase.

---

## 0. HOW TO USE THIS DOCUMENT

You (the human) will run these commands to Claude, one at a time:

```
Read BUILD_VOICE_AGENT.md and build Phase 1.
Read BUILD_VOICE_AGENT.md and build Phase 2.
... and so on through Phase 10.
```

**Rules for Claude (must follow on every phase):**
1. Read this whole file before writing any code.
2. Build **only the requested phase**. At the end of the phase, print a checklist of what was created and how to verify it.
3. Never use a paid API or paid cloud service. Everything runs locally / self-hosted (see §3 Non-Negotiables).
4. Write production-quality code: typed, documented, tested, no `TODO` stubs left behind for core paths.
5. Keep the code **modular** — the assistant must be embeddable into an existing website later with minimal changes.
6. Do not modify the existing company website. This is a **standalone app** that will later expose an embeddable widget.
7. Use the exact folder structure in §5. If you must deviate, explain why first.
8. Every phase must leave the project in a runnable/testable state.

---

## 1. PROJECT GOAL

Build a **standalone, self-hosted Voice AI Assistant** that:
- Accepts **voice input** and **text input**
- Responds with **text and voice simultaneously**
- The on-screen text and the spoken text are **always identical**
- Answers **only** from the company's own knowledge (RAG) — no hallucination
- Stores conversation history in the existing **Microsoft SQL Server**
- Later embeds into the company website as a **floating chat widget** with minimal integration effort

Two conversation modes: **Voice** and **Text**. Both must fully work.

---

## 2. COST MODEL (READ CAREFULLY)

- **The only thing the user pays for is the server** (a VM / on-prem machine with CPU or optional GPU).
- **Zero paid software/APIs.** No OpenAI, Claude, Gemini, ElevenLabs, Deepgram, Azure, or AWS AI services.
- All AI runs locally: STT, TTS, LLM, embeddings, vector DB.
- **Realistic hardware note (state this to the user, do not hide it):**
  - Minimum (usable, CPU-only): 8-core CPU, 16 GB RAM. Use small models (Qwen2.5 **3B**, Whisper **base/small**).
  - Recommended: any NVIDIA GPU with ≥8 GB VRAM. Enables Qwen2.5 **7B** and Whisper **medium/large-v3** with low latency.
  - The architecture must work on CPU-only and simply run faster on GPU. Model sizes are configurable via `.env`.

---

## 2A. RUN MODES (LOW-CONFIG DEV vs. SERVER) — MANDATORY

The project **must run in three modes**, selected by a single env var `RUN_MODE`. The developer has a **low-configuration PC** for building/testing and a **server** for real deployment. Docker is used **only on the server**; local development runs natively (no Docker). Switching modes must require **only `.env` changes — never code changes.**

| Mode (`RUN_MODE`) | Where | AI models | Docker? | Purpose |
|---|---|---|---|---|
| `stub` | low-config PC | **fake** responses (echo/canned) | ❌ no | Build & test the full flow (UI, streaming, WS, DB, history) with zero AI load |
| `local-light` | low-config PC | **tiny** models (Qwen2.5 **0.5B/1.5B**, Whisper **tiny/base**) | ❌ no | Verify real STT/TTS/LLM/RAG wiring on weak hardware — slow but functional |
| `docker-full` | server | **full** models (Qwen2.5 3B/7B, Whisper small→large) | ✅ yes | Production deployment via `docker compose up` |

**Implementation rules for Claude:**
1. Every AI service (`STTService`, `TTSService`, `LLMService`, `RAGService`/embedder) must have a **stub implementation** and a **real implementation** behind the same interface. `RUN_MODE=stub` binds the stubs via dependency injection — no real model is ever loaded.
2. All connection targets come from `.env` (e.g. `QDRANT_URL`, `OLLAMA_URL`, `SQL_CONN_STR`). Local uses `localhost`; Docker uses compose service names. **Same code, different `.env`.**
3. Model sizes come from env (`LLM_MODEL`, `WHISPER_MODEL`, `EMBED_MODEL`) so `local-light` and `docker-full` differ only by values.
4. Provide **three ready-made env files**: `.env.stub`, `.env.local`, `.env.docker` (all derived from `.env.example`). The developer copies one to `.env`.
5. If a real model fails to load on the low-config PC, the service must **fail loudly with a clear message** telling the user to switch to `stub` or use a smaller model — never crash silently.

### Local (no-Docker) developer workflow — document this in README

Provide native run instructions so the low-config PC never needs Docker:

```bash
# ---------- BACKEND (terminal 1) ----------
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
cp ../.env.stub .env          # start in stub mode (no AI load)
alembic upgrade head          # needs SQL Server reachable; see note below
uvicorn app.main:app --reload --port 8000

# ---------- FRONTEND (terminal 2) ----------
cd frontend
npm install
npm run dev                   # http://localhost:3000

# ---------- optional: Qdrant for local-light RAG ----------
# Qdrant can run as a single native binary OR one small docker container.
# For pure no-Docker dev, RAG can also fall back to an in-memory/on-disk
# Qdrant local mode (qdrant-client supports `:memory:` / local path).
```

**Notes for the low-config PC:**
- **SQL Server:** use your existing SQL Server, OR SQL Server Express (free) locally, OR — for the lightest dev — allow a `DB_BACKEND=sqlite` fallback so the app runs with **no SQL Server at all** during early UI testing. (Production always uses MS SQL Server.) Add a `sqlite` fallback in `db/session.py` gated by env.
- **Ollama:** for `local-light`, install Ollama natively and `ollama pull qwen2.5:0.5b`. For `stub`, Ollama isn't needed at all.
- **Qdrant:** `qdrant-client` supports a local (no-server) mode for dev; use it when `RUN_MODE != docker-full` so you don't need the Qdrant container on your PC.
- **Golden path for a weak machine:** start in `stub` → build/verify the entire app and UI → switch to `local-light` briefly to sanity-check real models → deploy `docker-full` on the server.

> Acceptance for every phase: the phase must be demonstrable in `stub` mode on a low-config PC **without Docker**, and must also work unchanged in `docker-full` mode by swapping `.env`.

---

## 3. NON-NEGOTIABLE TECH CHOICES (ALL FREE / OPEN SOURCE)

| Concern | Technology | Notes |
|---|---|---|
| Speech-to-Text | **faster-whisper** | CPU-friendly, multilingual, model size via env |
| Text-to-Speech | **Piper TTS** | Offline, fast, natural voices |
| LLM | **Qwen2.5-Instruct** via **Ollama** | 3B default (CPU) / 7B (GPU), configurable |
| Embeddings | **BAAI/bge-m3** | Multilingual, strong retrieval |
| Reranker (RAG quality) | **BAAI/bge-reranker-v2-m3** | Optional but recommended, free |
| Vector DB | **Qdrant** (Community) | Self-hosted via Docker |
| Voice Activity Detection | **Silero VAD** (+ `webrtcvad` fallback) | Free, for barge-in / silence detection |
| RAG orchestration | **LangChain** | Only where it adds value; keep core logic framework-independent |
| Backend | **FastAPI** + Pydantic v2 + async | REST + WebSocket |
| Frontend | **Next.js + React + TypeScript + Tailwind + React Query** | Widget-first |
| ORM / Migrations | **SQLAlchemy 2.x (async)** + **Alembic** | Against existing MS SQL Server |
| DB driver | **pyodbc / aioodbc** (MS SQL) | Do NOT replace SQL Server |
| Containerization | **Docker + Docker Compose** | One command to run everything |

> **Do NOT replace SQL Server.** Conversation history, sessions, feedback, analytics all live in MS SQL Server. Qdrant holds only vector embeddings of knowledge.

---

## 4. HIGH-LEVEL ARCHITECTURE

```
┌───────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                      │
│  Floating Chat Widget: Mic • Speaker • Text box • Send • Voice │
│  WebSocket (voice + streaming) • REST (history, feedback)      │
└───────────────┬───────────────────────────────────────────────┘
                │  WS / REST
┌───────────────▼───────────────────────────────────────────────┐
│                       BACKEND (FastAPI)                        │
│                                                                │
│  API Layer  ─────────────────────────────────────────────┐    │
│    /ws/voice   /ws/chat   /api/chat   /api/history  ...   │    │
│                                                          ▼     │
│  Service Layer (business logic, framework-independent)         │
│   ├─ STTService        (faster-whisper)                        │
│   ├─ TTSService        (Piper)                                 │
│   ├─ ConversationMgr   (orchestrates a turn)                   │
│   ├─ MemoryService     (SQL: sessions, messages)               │
│   ├─ RAGService        (embed → search → rerank → build prompt)│
│   ├─ LLMService        (Ollama / Qwen2.5, streaming)           │
│   └─ ValidationService (grounding / anti-hallucination checks) │
│                                                          │      │
│  Repository Layer (SQLAlchemy async)  ──────────────────┘      │
└──────┬───────────────────┬───────────────────────┬────────────┘
       │                   │                        │
┌──────▼──────┐   ┌────────▼────────┐     ┌─────────▼─────────┐
│  Ollama     │   │    Qdrant       │     │  MS SQL Server    │
│ (Qwen2.5)   │   │ (bge-m3 vectors)│     │ (existing DB)     │
└─────────────┘   └─────────────────┘     └───────────────────┘

Offline job:  INGESTION PIPELINE  → loads website/PDF/DOCX/FAQ/SQL
              → clean → chunk → embed (bge-m3) → upsert into Qdrant
              (runs only when source data changes)
```

**Turn flow (one user question):**
`Input (voice→STT or text)` → `ConversationManager` → `load memory` → `embed query` → `Qdrant search` → `rerank` → `PromptBuilder` → `LLM (stream)` → `Validation (grounding)` → `stream text to UI` → `TTS to audio` → `play audio` → `persist to SQL` → wait for next turn.

**Golden rule for identical text & voice:** the LLM produces the final text once. The UI displays *that exact string*, and TTS speaks *that exact string*. TTS input is never a paraphrase.

---

## 5. FOLDER STRUCTURE (CREATE EXACTLY THIS)

```
voice-agent/
├── README.md
├── BUILD_VOICE_AGENT.md          # this file
├── docker-compose.yml
├── docker-compose.gpu.yml        # override for GPU
├── .env.example
├── Makefile                      # convenience commands
│
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/                  # migrations
│   ├── app/
│   │   ├── main.py               # FastAPI app factory + lifespan
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic Settings (env-driven)
│   │   │   ├── logging.py        # structured logging
│   │   │   ├── security.py       # auth-ready hooks, CORS
│   │   │   ├── rate_limit.py
│   │   │   └── exceptions.py     # app exceptions + handlers
│   │   ├── api/
│   │   │   ├── deps.py           # dependency injection
│   │   │   ├── rest/
│   │   │   │   ├── chat.py
│   │   │   │   ├── history.py
│   │   │   │   ├── feedback.py
│   │   │   │   └── health.py
│   │   │   └── ws/
│   │   │       ├── chat_ws.py    # text streaming
│   │   │       └── voice_ws.py   # audio in/out, barge-in
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── stt_service.py
│   │   │   ├── tts_service.py
│   │   │   ├── llm_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── conversation_manager.py
│   │   │   ├── memory_service.py
│   │   │   └── validation_service.py
│   │   ├── rag/
│   │   │   ├── embedder.py        # bge-m3
│   │   │   ├── reranker.py        # bge-reranker-v2-m3
│   │   │   ├── vector_store.py    # Qdrant client wrapper
│   │   │   └── prompt_builder.py  # anti-hallucination prompt
│   │   ├── db/
│   │   │   ├── session.py         # async engine/session
│   │   │   ├── base.py
│   │   │   ├── models/            # SQLAlchemy ORM models
│   │   │   └── repositories/      # repository pattern
│   │   └── utils/
│   ├── ingestion/
│   │   ├── run_ingestion.py       # CLI entrypoint
│   │   ├── loaders/
│   │   │   ├── website_loader.py
│   │   │   ├── pdf_loader.py
│   │   │   ├── docx_loader.py
│   │   │   ├── faq_loader.py
│   │   │   └── sql_loader.py
│   │   ├── cleaning.py
│   │   ├── chunking.py
│   │   └── pipeline.py
│   ├── scripts/
│   │   ├── download_models.py     # whisper, piper voices, bge-m3
│   │   └── seed_ollama.sh         # ollama pull qwen2.5
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── api/
│
├── frontend/
│   ├── package.json
│   ├── Dockerfile
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/                   # Next.js app router (demo host page)
│   │   ├── widget/                # the embeddable widget (self-contained)
│   │   │   ├── ChatWidget.tsx
│   │   │   ├── VoiceButton.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── VoiceWave.tsx
│   │   │   └── index.ts           # mount() export for embedding
│   │   ├── hooks/
│   │   │   ├── useChatSocket.ts
│   │   │   ├── useVoiceSocket.ts
│   │   │   ├── useRecorder.ts      # MediaRecorder + VAD
│   │   │   └── useAudioPlayer.ts
│   │   ├── lib/                    # api client, ws client, types
│   │   └── styles/
│   └── public/
│
├── models/                        # downloaded model files (gitignored)
├── data/                          # source docs to ingest (gitignored)
└── deploy/
    ├── nginx/                      # reverse proxy config
    └── README.md                   # deployment + website embed guide
```

---

## 6. DATABASE DESIGN (MS SQL SERVER)

Create these tables via **Alembic** migrations (schema `voiceai` to avoid clashing with existing tables). Use GUID/`UNIQUEIDENTIFIER` or BIGINT identity — match existing company convention; default to `UNIQUEIDENTIFIER`.

- **`voiceai.sessions`** — `id`, `user_ref` (nullable, links to existing auth later), `channel` (voice/text), `created_at`, `last_active_at`, `metadata` (JSON), `is_active`.
- **`voiceai.messages`** — `id`, `session_id` (FK), `role` (user/assistant/system), `content` (final text = what was displayed AND spoken), `input_type` (voice/text), `created_at`, `latency_ms`, `token_usage` (JSON, nullable).
- **`voiceai.retrievals`** — `id`, `message_id` (FK), `chunk_id`, `source`, `score`, `used` (bool) — audit of what context grounded each answer.
- **`voiceai.feedback`** — `id`, `message_id` (FK), `rating` (up/down), `comment`, `created_at`.
- **`voiceai.analytics`** — `id`, `session_id`, `event_type`, `payload` (JSON), `created_at` — for the future dashboard.
- **`voiceai.user_preferences`** — `id`, `user_ref`, `theme`, `voice_enabled`, `tts_voice`, `language`, `updated_at`.
- **`voiceai.audit_logs`** — `id`, `actor`, `action`, `entity`, `entity_id`, `ip`, `created_at`.

> Do not touch existing tables. All new tables live under the `voiceai` schema. Provide a rollback migration.

---

## 7. ANTI-HALLUCINATION CONTRACT (CRITICAL)

1. **Always retrieve** before answering. No direct-from-model answers.
2. Prompt (in `prompt_builder.py`) must state: *"Answer ONLY using the CONTEXT below. If the answer is not in the context, reply exactly: 'I don't have that information.' Never invent facts, prices, policies, or links."*
3. **ValidationService** runs after generation:
   - If retrieval returned nothing above the score threshold → force the "I don't have that information." response.
   - Optional grounding check: verify the answer's claims overlap with retrieved context; if not, downgrade to the safe fallback.
4. Store retrieved chunks in `voiceai.retrievals` for auditability.
5. Config knobs in `.env`: `RAG_TOP_K`, `RAG_SCORE_THRESHOLD`, `RAG_USE_RERANKER`, `RAG_MIN_CONTEXT_CHARS`.

---

## 8. API SURFACE (DESIGN IN PHASE 4)

**REST**
- `GET /api/health` — liveness + dependency checks (Ollama, Qdrant, SQL).
- `POST /api/chat` — non-streaming text turn (request: `{session_id?, message, input_type}` → response: `{session_id, answer, sources[], latency_ms}`).
- `GET /api/history/{session_id}` — paginated messages.
- `POST /api/feedback` — `{message_id, rating, comment?}`.
- `POST /api/session` / `DELETE /api/session/{id}` (clear conversation).
- `GET /api/suggestions` — suggested starter questions.

**WebSocket**
- `WS /ws/chat` — streamed text turn (tokens streamed as they generate).
- `WS /ws/voice` — bidirectional: client streams mic audio frames → server does VAD + STT → runs turn → streams back `{type: "partial_text"|"final_text"|"audio_chunk"|"done"}`; supports **barge-in** (client sends `interrupt`, server stops TTS/LLM).

Every schema defined with Pydantic; document via FastAPI OpenAPI at `/docs`.

---

## 9. THE 10 BUILD PHASES

For **every** phase, Claude must document: **Purpose · Design Decisions · Best Practices · Scalability · Security · Future Improvements**, then produce the code, then a **verification checklist**.

### Phase 1 — Architecture & Project Scaffold
- Create repo skeleton (§5), `README.md`, `.env.example` plus the three mode files `.env.stub` / `.env.local` / `.env.docker` (see §2A), `Makefile`, `pyproject.toml`, `package.json`, `.gitignore`.
- Wire `RUN_MODE` into `core/config.py` so `stub` / `local-light` / `docker-full` are selectable from day one.
- Write an `ARCHITECTURE.md` documenting the diagram (§4), data flow, and component contracts.
- No business logic yet — just a clean, documented, runnable skeleton (FastAPI "hello", Next.js "hello").
- **Verify:** `docker compose up` starts empty backend + frontend; `/api/health` returns 200.

### Phase 2 — Folder Structure & Configuration Layer
- Implement `core/config.py` (Pydantic Settings), `core/logging.py`, `core/exceptions.py`, `core/security.py` (CORS + auth-ready hooks), `core/rate_limit.py`.
- Implement DI (`api/deps.py`) and app factory (`main.py`) with lifespan startup/shutdown.
- **Verify:** app boots with structured logs; config loads from `.env`; health check reports each dependency's status.

### Phase 3 — Database Design (SQL Server)
- SQLAlchemy async models (§6), Alembic setup, initial migration creating the `voiceai` schema + tables.
- Repository pattern classes for each entity.
- **Verify:** `alembic upgrade head` creates tables in SQL Server; `alembic downgrade` cleanly rolls back; repository unit tests pass against a test DB.

### Phase 4 — Backend Core (APIs + Services skeleton + Memory)
- REST + WebSocket routes (§8) with full Pydantic schemas.
- `ConversationManager`, `MemoryService` (persist sessions/messages to SQL), service interfaces for STT/TTS/LLM/RAG (mockable).
- **Verify:** text chat works end-to-end with a **stub LLM** (echo), history persists to SQL, `/docs` shows all endpoints.

### Phase 5 — Frontend (Widget + Chat UI)
- Floating chat widget: message list, streaming text, typing/thinking indicators, markdown + code highlighting, suggested questions, clear conversation, dark/light mode, responsive (desktop/tablet/mobile).
- Voice UI: mic button, speaker/mute, stop-speaking, voice-wave animation.
- Hooks: `useChatSocket`, `useVoiceSocket`, `useRecorder` (MediaRecorder + VAD), `useAudioPlayer`.
- `widget/index.ts` exposes a `mount(elementId, config)` for later website embedding.
- **Verify:** widget talks to Phase-4 backend over WS; text streaming visible; UI responsive and themeable.

### Phase 6 — RAG (Ingestion + Retrieval)
- Ingestion pipeline CLI: website/PDF/DOCX/FAQ/SQL loaders → clean → chunk → **bge-m3** embed → upsert to **Qdrant** (with metadata: source, url, type). Runs only on data change; supports incremental re-index via content hashes.
- Retrieval: `RAGService` = embed query → Qdrant search → **bge-reranker** → build grounded prompt (§7).
- Wire real RAG into `ConversationManager`.
- **Verify:** run ingestion on sample docs; ask a question answered only from a doc; ask an out-of-scope question → get "I don't have that information."; retrievals logged to SQL.

### Phase 7 — Voice (STT + TTS + real LLM)
- `STTService` (faster-whisper), `TTSService` (Piper), swap stub LLM for **Ollama/Qwen2.5** streaming.
- `WS /ws/voice`: mic frames → VAD (silence detection, auto-stop) → STT → turn → stream final text → Piper TTS → audio back. Implement **barge-in** (interrupt LLM+TTS), push-to-talk, and continuous-listening modes.
- Enforce identical-text-and-voice rule (§4 golden rule).
- **Verify:** full spoken conversation works; interrupting mid-answer stops speech; displayed text === spoken text.

### Phase 8 — Deployment (Docker Compose)
- `docker-compose.yml` services: `backend`, `frontend`, `qdrant`, `ollama` (SQL Server is external/existing — connect via env). GPU override file. Model download on first run (`scripts/download_models.py`, `seed_ollama.sh`).
- Nginx reverse proxy in `deploy/`; healthchecks; volumes for models & Qdrant storage.
- **Verify:** `docker compose up` on a clean machine brings up the whole stack; documented resource requirements; `/api/health` ll-green.a

### Phase 9 — Testing & Monitoring
- Unit tests (services, RAG, validation), integration tests (DB, Qdrant), API tests (REST + WS). Target meaningful coverage on core paths.
- Health check API, structured logs, latency/error/conversation metrics (Prometheus-style `/metrics` endpoint, free).
- **Verify:** test suite passes in CI-style run; metrics endpoint exposes latency & error counts.

### Phase 10 — Website Integration
- Build the widget as an embeddable bundle. Provide a **one-snippet embed**:
  ```html
  <script src="https://YOUR_SERVER/widget.js" defer></script>
  <div id="voice-ai-widget" data-api="https://YOUR_SERVER"></div>
  ```
- Document CORS/allowed-origins config, auth handoff (map existing website user → `user_ref`), and theming to match the site.
- **Deliverable:** `deploy/README.md` integration guide. **No changes to existing website code beyond adding the snippet.**
- **Verify:** widget loads on a plain HTML page pointing at the deployed backend and works end-to-end.

---

## 10. CROSS-CUTTING REQUIREMENTS (apply in every phase)

- **Clean Architecture:** API → Service → Repository. Business logic never depends on FastAPI or LangChain directly.
- **Dependency Injection** everywhere; services are interface-driven and mockable.
- **Config via env only** (`.env`), never hardcode secrets. Provide `.env.example`.
- **Security:** input validation (Pydantic), rate limiting, CORS allowlist, auth-ready middleware (JWT hook stub), audit logging, secrets from env.
- **Observability:** structured JSON logs, request IDs, latency timing per turn, error logs, conversation logs.
- **Error handling:** typed exceptions + global handlers; graceful degradation (e.g., TTS fails → still return text).
- **Modularity for embedding:** frontend widget is self-contained; backend origin is configurable.
- **No paid services. Ever.** If a free option is missing, ask the user before introducing any dependency with a cost.

---

## 11. FUTURE EXTENSIONS (design seams now, implement later)

Human-agent transfer · CRM integration · order tracking · ticket generation · appointment booking · email integration · analytics dashboard · admin panel. Leave clean interfaces (e.g., a `ToolRegistry` in the service layer and event hooks in `analytics`) so these plug in without refactors.

---

## 12. DEFINITION OF DONE

- All 10 phases complete, each documented (Purpose/Design/Best Practices/Scalability/Security/Future).
- Runs in all three modes (§2A): `stub` and `local-light` **without Docker** on a low-config PC, and `docker-full` on the server — switching modes changes **only `.env`**, never code.
- `docker compose up` runs the entire stack on a fresh server with only `.env.docker` copied to `.env`.
- Voice + text both fully functional; answers grounded in company knowledge; out-of-scope → safe fallback.
- Conversation history in SQL Server; embeddings in Qdrant; zero paid dependencies.
- Widget embeds into an external page via one snippet, no existing-website code changes.
```
