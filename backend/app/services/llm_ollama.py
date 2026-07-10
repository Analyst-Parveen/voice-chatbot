"""Ollama-backed LLM service (Qwen2.5-Instruct).

Streams tokens from a local Ollama server over its HTTP API. Implements the
same ``LLMService`` interface as the stub, so the ConversationManager is
unchanged. Selected when ``RUN_MODE`` is not ``stub``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.dto import LLMRequest

logger = get_logger(__name__)


class OllamaLLMService:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.ollama_url.rstrip("/")
        self._model = settings.llm_model
        self._timeout = httpx.Timeout(
            connect=10.0,
            read=settings.ollama_timeout_seconds,
            write=30.0,
            pool=10.0,
        )

    def _messages(self, request: LLMRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": request.system}]
        for turn in request.history:
            messages.append({"role": turn.role, "content": turn.content})
        # Fold retrieved context into the user turn so the model answers from it.
        if request.context:
            user = f"{request.context}\n\nQuestion: {request.user_message}"
        else:
            user = request.user_message
        messages.append({"role": "user", "content": user})
        return messages

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": self._messages(request),
            "stream": True,
            "options": {"temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", f"{self._url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break

    async def complete(self, request: LLMRequest) -> str:
        parts: list[str] = []
        async for chunk in self.stream(request):
            parts.append(chunk)
        return "".join(parts)
