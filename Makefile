# Voice AI Assistant — convenience commands
# Works with GNU make. On Windows use Git Bash / WSL, or run the raw
# commands shown in each target.

.PHONY: help mode-stub mode-local mode-docker \
        backend-install backend-dev frontend-install frontend-dev \
        up down logs test lint

help:
	@echo "Voice AI Assistant — available commands:"
	@echo "  make mode-stub        Copy .env.stub   -> .env (no AI, no Docker)"
	@echo "  make mode-local       Copy .env.local  -> .env (tiny models, no Docker)"
	@echo "  make mode-docker      Copy .env.docker -> .env (full stack, Docker)"
	@echo "  make backend-install  Create venv + install backend deps"
	@echo "  make backend-dev      Run FastAPI with autoreload (port 8000)"
	@echo "  make frontend-install Install frontend deps"
	@echo "  make frontend-dev     Run Next.js dev server (port 3000)"
	@echo "  make up               docker compose up (server)"
	@echo "  make down             docker compose down"
	@echo "  make logs             Tail compose logs"
	@echo "  make test             Run backend tests"
	@echo "  make lint             Run backend linters"

# ---- Mode switching ----
mode-stub:
	cp .env.stub .env
mode-local:
	cp .env.local .env
mode-docker:
	cp .env.docker .env

# ---- Backend (native, no Docker) ----
backend-install:
	cd backend && python -m venv .venv && \
	. .venv/bin/activate && pip install -e ".[dev]"
backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ---- Frontend (native, no Docker) ----
frontend-install:
	cd frontend && npm install
frontend-dev:
	cd frontend && npm run dev

# ---- Docker (server) ----
up:
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f

# ---- Quality ----
test:
	cd backend && pytest -q
lint:
	cd backend && ruff check . && mypy app
