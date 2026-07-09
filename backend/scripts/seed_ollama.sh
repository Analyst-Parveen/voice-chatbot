#!/usr/bin/env bash
# Pull the LLM into Ollama. Run against a running Ollama server.
#
#   From the host (Ollama in compose):
#     docker compose exec ollama ollama pull qwen2.5:3b
#   Or standalone:
#     LLM_MODEL=qwen2.5:3b OLLAMA_URL=http://localhost:11434 ./seed_ollama.sh
set -e

MODEL="${LLM_MODEL:-qwen2.5:3b}"
HOST="${OLLAMA_URL:-http://localhost:11434}"

echo "Pulling '${MODEL}' via ${HOST}…"
OLLAMA_HOST="${HOST}" ollama pull "${MODEL}"
echo "Done."
