# Voice AI Assistant — convenience commands
# Works with GNU make. On Windows use Git Bash / WSL, or run the raw
# commands shown in each target.

.PHONY: help mode-stub mode-local mode-azure \
        backend-install backend-dev frontend-install frontend-dev \
        test lint

help:
	@echo "Voice AI Assistant — available commands:"
	@echo "  make mode-stub        Copy .env.stub  -> .env (no AI — fast UI testing)"
	@echo "  make mode-local       Copy .env.local -> .env (tiny models, dev PC)"
	@echo "  make mode-azure       Copy .env.azure -> .env (full models, server VM)"
	@echo "  make backend-install  Create venv + install backend deps"
	@echo "  make backend-dev      Run FastAPI with autoreload (port 8000)"
	@echo "  make frontend-install Install frontend deps"
	@echo "  make frontend-dev     Run Next.js dev server (port 3000)"
	@echo "  make test             Run backend tests"
	@echo "  make lint             Run backend linters"
	@echo ""
	@echo "Server deployment (no Docker): see deploy/azure/README.md"

# ---- Mode switching ----
mode-stub:
	cp .env.stub .env
mode-local:
	cp .env.local .env
mode-azure:
	cp .env.azure .env

# ---- Backend (native) ----
backend-install:
	cd backend && python -m venv .venv && \
	. .venv/bin/activate && pip install -e ".[dev]"
backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ---- Frontend (native) ----
frontend-install:
	cd frontend && npm install
frontend-dev:
	cd frontend && npm run dev

# ---- Quality ----
test:
	cd backend && pytest -q
lint:
	cd backend && ruff check . && mypy app
