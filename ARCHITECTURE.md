# Architecture

This document describes the design of the Voice AI Assistant: the components,
how a conversation turn flows through them, the contracts between layers, and
the principles that keep the system modular, testable, and free to run.

---

## 1. Design goals

1. **Standalone first, embeddable later.** Runs as its own app; later ships a
   self-contained widget that drops into the company website with one snippet
   and zero changes to existing site code.
2. **Grounded answers only.** Every response is built from retrieved company
   knowledge (RAG). Out-of-scope questions get a safe fallback, never a guess.
3. **Identical text & voice.** The LLM produces the final answer string once;
   the UI displays *that exact string* and TTS speaks *that exact string*.
4. **100% free / self-hosted.** No paid APIs. All AI runs locally.
5. **Runs on weak and strong hardware.** A `RUN_MODE` switch (`stub` /
   `local-light` / `docker-full`) changes behavior via env only, never code.
6. **Clean architecture.** API → Service → Repository. Business logic never
   depends on FastAPI, LangChain, or any vendor SDK directly.

---

## 2. Component diagram

```
┌───────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                      │
│  Floating Chat Widget: Mic • Speaker • Text box • Send • Voice │
│  WebSocket (voice + streaming) • REST (history, feedback)      │
└───────────────┬───────────────────────────────────────────────┘
                │  WS / REST
┌───────────────▼───────────────────────────────────────────────┐
│                       BACKEND (FastAPI)                        │
│  API Layer:   /ws/voice  /ws/chat  /api/chat  /api/history ... │
│  Service Layer (framework-independent business logic):         │
│    STTService · TTSService · ConversationManager ·             │
│    MemoryService · RAGService · LLMService · ValidationService │
│  Repository Layer (SQLAlchemy async)                           │
└──────┬───────────────────┬───────────────────────┬────────────┘
       │                   │                        │
┌──────▼──────┐   ┌────────▼────────┐     ┌─────────▼─────────┐
│  Ollama     │   │    Qdrant       │     │  MS SQL Server    │
│ (Qwen2.5)   │   │ (bge-m3 vectors)│     │ (existing DB)     │
└─────────────┘   └─────────────────┘     └───────────────────┘

Offline job: INGESTION PIPELINE → website/PDF/DOCX/FAQ/SQL
             → clean → chunk → embed (bge-m3) → upsert into Qdrant
             (runs only when source data changes)
```

---

## 3. Layered responsibilities

| Layer | Responsibility | Knows about |
|---|---|---|
| **API** (`app/api`) | HTTP/WS transport, request/response schemas, auth, rate limiting | Services (via DI) |
| **Service** (`app/services`) | Business logic; orchestrates a turn | Repositories, RAG, model adapters (via interfaces) |
| **Repository** (`app/db/repositories`) | Data access to SQL Server | SQLAlchemy models only |
| **Adapters** (`app/rag`, model clients) | Talk to Qdrant / Ollama / Whisper / Piper | External systems |

The Service layer depends on **interfaces**, not concrete implementations, so
`stub` mode swaps in fake adapters through dependency injection.

---

## 4. Conversation turn flow

```
Input (voice → STT, or text)
  → ConversationManager
    → MemoryService.load(session)          # recent history from SQL
    → RAGService.retrieve(query)           # embed → Qdrant search → rerank
    → PromptBuilder.build(history, context)# anti-hallucination prompt
    → LLMService.stream(prompt)            # Qwen2.5 tokens
    → ValidationService.check(answer, ctx) # grounding / safe fallback
    → stream final text to UI
    → TTSService.speak(final_text)         # identical string → audio
    → MemoryService.persist(turn)          # SQL: message + retrievals
  → wait for next turn
```

**Anti-hallucination contract:** always retrieve; prompt restricts answers to
context; if retrieval is empty/low-score or the answer isn't grounded, return
exactly `"I don't have that information."` Retrieved chunks are logged to
`voiceai.retrievals` for audit.

---

## 5. Run modes (env-driven)

| `RUN_MODE` | STT | TTS | LLM | Vector DB | DB | Docker |
|---|---|---|---|---|---|---|
| `stub` | fake | fake | echo | in-memory | SQLite | no |
| `local-light` | Whisper tiny | Piper low | Qwen 0.5B (Ollama) | embedded Qdrant | SQLite/MSSQL | no |
| `docker-full` | Whisper small+ | Piper medium | Qwen 3B/7B (Ollama) | Qdrant service | MS SQL Server | yes |

Selection happens in `app/core/config.py`; adapters are chosen in
`app/api/deps.py` (dependency injection). Application code is identical across
modes.

---

## 6. Data stores

- **Microsoft SQL Server** (existing) — sessions, messages, retrievals audit,
  feedback, analytics, user preferences, audit logs. Under a dedicated
  `voiceai` schema so nothing collides with existing tables. A `sqlite`
  fallback exists **only** for lightweight local dev.
- **Qdrant** — embeddings of company knowledge with metadata (source, url,
  type). The only place vectors live; never business data.

---

## 7. Component contracts (interfaces, implemented in later phases)

```text
STTService.transcribe(audio: bytes, lang?) -> Transcript
TTSService.synthesize(text: str, voice?) -> AudioStream
LLMService.stream(prompt: Prompt) -> AsyncIterator[str]
RAGService.retrieve(query: str, top_k, threshold) -> list[Chunk]
MemoryService.load(session_id) / persist(turn)
ValidationService.check(answer, context) -> ValidatedAnswer
ConversationManager.handle_text(...) / handle_voice(...)
```

Each has a **stub** and a **real** implementation behind the same interface.

---

## 8. Cross-cutting concerns

- **Config**: Pydantic Settings, env-only, no hardcoded secrets.
- **Logging**: structured (JSON in prod), request IDs, per-turn latency.
- **Security**: input validation, rate limiting, CORS allowlist, auth-ready
  middleware (JWT hook), audit logging.
- **Errors**: typed exceptions + global handlers; graceful degradation (e.g.
  TTS failure still returns text).
- **Observability**: health checks now; `/metrics` (latency/errors) in Phase 9.

---

## 9. Website integration (Phase 10)

The widget builds to a standalone bundle mounted via:

```html
<script src="https://YOUR_SERVER/widget.js" defer></script>
<div id="voice-ai-widget" data-api="https://YOUR_SERVER"></div>
```

Backend origin, CORS allowlist, and theming are configurable. Existing website
users map to `user_ref` for history — no changes to existing site code beyond
adding the snippet.

---

## 10. Build phases

See [`BUILD_VOICE_AGENT.md`](BUILD_VOICE_AGENT.md). Phases: architecture →
folder/config → database → backend core → frontend → RAG → voice → deployment
→ testing/monitoring → website integration.
