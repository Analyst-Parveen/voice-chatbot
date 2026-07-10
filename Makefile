# Voice AI Assistant — convenience commands

.PHONY: help mode-stub mode-local mode-azure \
        backend-install backend-dev frontend-install frontend-dev \
        test lint

help:
	@echo "Voice AI Assistant — available commands:"
	@echo "  make mode-stub        Copy backend/.env.stub -> backend/.env"
	@echo "  make mode-local       Copy backend/.env.local -> backend/.env"
	@echo "  make mode-azure       Copy backend/.env.azure -> backend/.env"
	@echo "  make backend-install  Create venv + install backend deps"
	@echo "  make backend-dev      Run FastAPI with autoreload (port 8000)"
	@echo "  make frontend-install Install frontend deps"
	@echo "  make frontend-dev     Run Next.js dev server (port 3000)"
	@echo "  make test             Run backend tests"
	@echo "  make lint             Run backend linters"
	@echo ""
	@echo "Server deployment: see backend/deploy/azure/README.md"

mode-stub:
	cp backend/.env.stub backend/.env
mode-local:
	cp backend/.env.local backend/.env
mode-azure:
	cp backend/.env.azure backend/.env

backend-install:
	cd backend && python -m venv .venv && \
	. .venv/bin/activate && pip install -r requirements.txt
backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-install:
	cd frontend && npm install
frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && pytest -q
lint:
	cd backend && ruff check . && mypy app
