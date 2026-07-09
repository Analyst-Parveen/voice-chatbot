"""Response validation — the anti-hallucination gate.

Enforces the contract from §7 of the build spec: an answer must be grounded in
retrieved context. When it isn't, the assistant returns the safe fallback
instead of guessing.

Phase 4 implements the *structural* gate (is there enough context?). Phase 6
adds semantic grounding (does the answer's content actually appear in the
context?). In ``stub`` mode the gate is relaxed so the echo flow is testable.
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.dto import RetrievedChunk

FALLBACK_MESSAGE = "I don't have that information."
HINDI_FALLBACK_MESSAGE = "Mere paas yeh jaankari nahi hai."
HINDI_FALLBACK_DEVANAGARI = "मेरे पास यह जानकारी नहीं है।"


def hindi_fallback_message(devanagari: bool = False) -> str:
    return HINDI_FALLBACK_DEVANAGARI if devanagari else HINDI_FALLBACK_MESSAGE


class ValidationService:
    """Decides whether the assistant may answer, and applies the fallback."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def should_answer(self, chunks: list[RetrievedChunk]) -> bool:
        """True if there is sufficient grounding context to answer.

        When RAG is disabled (echo/dev mode) there is no knowledge base to ground
        against, so we allow the response. When RAG is enabled, enforce the
        anti-hallucination contract: require at least one chunk over the score
        threshold with enough combined context length.
        """
        if not self._settings.rag_enabled:
            return True
        strong = [c for c in chunks if c.score >= self._settings.rag_score_threshold]
        if not strong:
            return False
        total_chars = sum(len(c.text) for c in strong)
        return total_chars >= self._settings.rag_min_context_chars

    def is_grounded(self, chunk: RetrievedChunk) -> bool:
        """Whether a single chunk cleared the score threshold (for audit)."""
        return chunk.score >= self._settings.rag_score_threshold

    def finalize_answer(self, answer: str, chunks: list[RetrievedChunk]) -> str:
        """Return the answer, or the fallback if grounding is insufficient."""
        if not self.should_answer(chunks):
            return FALLBACK_MESSAGE
        return answer
