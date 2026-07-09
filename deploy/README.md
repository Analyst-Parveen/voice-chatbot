# Deployment Guide

Bring up the whole Voice AI Assistant stack on a server with Docker Compose.
The frontend, backend, Qdrant, and Ollama run as containers; **your existing
Microsoft SQL Server stays external** and is reached via `MSSQL_*` env vars.

---

## 1. Prerequisites

- Docker Engine + Docker Compose v2
- Network access from the server to your SQL Server
- (Optional) NVIDIA GPU + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) for low-latency voice/LLM

## 2. Resource requirements

| Profile | CPU / GPU | RAM | Notes |
|---|---|---|---|
| **Minimum (CPU-only)** | 8 vCPU | 16 GB | Qwen2.5 **3B**, Whisper **small**, bge-m3. Voice replies feel slow. |
| **Comfortable** | 8 vCPU + NVIDIA GPU ≥ 8 GB VRAM | 16–32 GB | Near real-time voice; Qwen 7B possible. |
| Disk | — | ~15 GB free | Model weights: Qwen 3B ≈ 2 GB, bge-m3 ≈ 2 GB, Whisper ≈ 0.5 GB, images. |

The stack works CPU-only and simply runs faster on a GPU (see §6).

## 3. Configure

```bash
cp .env.docker .env
```
Edit `.env` and set at least:
- `MSSQL_HOST`, `MSSQL_DB`, `MSSQL_USER`, `MSSQL_PASSWORD` — your SQL Server
- `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_BASE_URL` — the **public** URL of
  this server as the browser will reach it, e.g. `https://assistant.acme.com`
  and `wss://assistant.acme.com` (these are baked into the frontend at build time)
- `CORS_ORIGINS` — your website origin(s)
- `JWT_SECRET` — a long random string
- `LLM_MODEL` — e.g. `qwen2.5:3b` (or `qwen2.5:7b` on a GPU)

## 4. Launch

```bash
docker compose up -d --build
```

On first boot the stack will:
1. start Qdrant and Ollama,
2. `ollama-init` pulls the LLM (`LLM_MODEL`) into Ollama,
3. the backend downloads the Piper voice, applies DB migrations, and starts,
4. nginx serves everything on **port 80**.

Whisper and bge-m3 download on first use and are cached in the `hf_cache` volume.

Check health:
```bash
curl http://localhost/api/health      # expect status "ok", all deps reachable
docker compose ps                      # all services up; ollama healthy
```
Open `http://<server>/` for the widget, `http://<server>/docs` for the API.

## 5. Ingest knowledge

Put your PDFs / DOCX / FAQs / markdown in `./data`, then:
```bash
docker compose exec backend python -m ingestion.run_ingestion --data-dir ./data
```
Re-run whenever the source data changes (it re-embeds only what changed).

## 6. GPU

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```
Gives Ollama and the backend GPU access; the backend uses CUDA for Whisper via
`WHISPER_DEVICE=cuda` (set automatically by the override).

## 7. Common operations

```bash
docker compose logs -f backend         # tail backend logs
docker compose restart backend         # restart after an .env change
docker compose exec ollama ollama list # verify the model is present
docker compose down                    # stop (volumes/data preserved)
```

## 8. TLS

Terminate TLS in front of the `nginx` service (another nginx, a cloud load
balancer, or Caddy) and use `https://` / `wss://` in `NEXT_PUBLIC_*`. The
included nginx config listens on plain `:80` for the internal edge.

## 9. Website integration (embed the widget)

The assistant ships as a standalone **`widget.js`** bundle (React + styles are
bundled in and rendered inside a **Shadow DOM**, so it's fully isolated from your
site's CSS and vice-versa). Embedding it requires **no changes to your existing
website code** beyond adding one snippet.

### 9.1 The snippet

Add this to any page (e.g. before `</body>`):

```html
<script src="https://YOUR_SERVER/widget.js" defer></script>
<div id="voice-ai-widget"
     data-api="https://YOUR_SERVER"
     data-title="Company Assistant"
     data-subtitle="Ask me anything"
     data-accent="#4f46e5"
     data-position="bottom-right"
     data-theme="auto"></div>
```

`widget.js` is served by this stack at `/widget.js` (through nginx → frontend).
A working example page is served at `https://YOUR_SERVER/embed-demo.html`.

### 9.2 Configuration (`data-*` attributes)

| Attribute | Meaning | Default |
|---|---|---|
| `data-api` | Backend base URL. WS URL is derived (`http→ws`). | required |
| `data-ws` | Override WS base URL explicitly (e.g. `wss://…`). | derived from `data-api` |
| `data-title` / `data-subtitle` | Header text. | "AI Assistant" |
| `data-accent` | Accent color (hex). | `#4f46e5` |
| `data-position` | `bottom-right` \| `bottom-left`. | `bottom-right` |
| `data-theme` | `auto` \| `light` \| `dark`. | `auto` |
| `data-voice` | `false` disables the mic. | enabled |
| `data-user-ref` | Attribute conversations to a site user (see §9.4). | — |
| `data-token` | JWT for authenticated REST calls (see §9.4). | — |

### 9.3 Imperative mount (optional)

If you prefer JS control (SPAs, dynamic user info):

```html
<script src="https://YOUR_SERVER/widget.js" defer></script>
<script>
  window.addEventListener("load", () => {
    VoiceAI.mount("voice-ai-widget", {
      apiBaseUrl: "https://YOUR_SERVER",
      wsBaseUrl: "wss://YOUR_SERVER",
      userRef: currentUser?.id,      // your logged-in user id
      token: currentUser?.jwt,       // optional
      theme: "auto",
    });
  });
  // VoiceAI.unmount("voice-ai-widget") to remove it.
</script>
```

### 9.4 Auth handoff (mapping your site user → `user_ref`)

Conversations are stored per session in SQL Server with an optional `user_ref`.
There are two levels:

- **Soft attribution** — pass `data-user-ref` / `userRef`. The widget includes it
  with each turn so sessions and history are tied to that user. Simple, but the
  value is client-supplied (trust it only for non-sensitive attribution).
- **Verified (recommended for anything sensitive)** — set `AUTH_ENABLED=true`,
  issue your site's JWT, and pass it as `data-token` / `token`. The backend
  verifies it and derives `user_ref` from the verified claims. Replace the
  placeholder verifier in `app/core/security.py::verify_token` with real JWT
  validation against your signing key (that's the single wiring point).

### 9.5 CORS / allowed origins

Set `CORS_ORIGINS` in `.env` to your website origin(s), comma-separated:

```env
CORS_ORIGINS=https://www.acme.com,https://acme.com
```

Because the widget calls the API cross-origin (your site → this server), the
origin must be allowlisted. Restart the backend after changing it.

### 9.6 Theming

`data-accent` recolors the launcher, header, buttons, and links. `data-theme`
follows the visitor's OS (`auto`) or forces `light`/`dark`. For deeper brand
matching, edit `frontend/src/embed/widget.css` and rebuild
(`npm run build:widget`) — styles are scoped to the widget's Shadow DOM.

### 9.7 Rebuilding the bundle

`widget.js` is produced by `npm run build:widget` and is rebuilt automatically
inside the frontend Docker image. After changing widget code or styles, redeploy
the frontend service (or run the build and serve `frontend/public/widget.js`).
