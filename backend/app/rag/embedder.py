"""Text embedders.

Two implementations behind one interface:

- ``LexicalEmbedder`` — a dependency-free, feature-hashed bag-of-words vectorizer
  (unigrams + bigrams, L2-normalized). Cosine similarity reflects term overlap,
  so keyword-style retrieval works well. Runs instantly on any CPU with no model
  download — ideal for a low-config dev PC and for tests.
- ``BgeEmbedder`` — the real multilingual ``BAAI/bge-m3`` model via
  sentence-transformers (semantic retrieval). Heavy (PyTorch); used in
  production. Imported lazily so the dependency is only needed when selected.

``get_embedder`` picks one based on ``EMBED_MODEL`` / run mode.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common English function words. Removing them makes lexical similarity reflect
# CONTENT overlap, so questions that merely share "how do I … to" don't falsely
# match unrelated documents. (bge-m3 handles this semantically in production.)
_STOPWORDS = frozenset(
    """a an and are as at be but by can could do does for from had has have how i
    in is it its me my of on or our so that the their them then there these they
    this to was we what when where which who will with would you your""".split()
)


class Embedder(Protocol):
    dimension: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LexicalEmbedder:
    """Feature-hashed bag-of-words embedder (unigrams + bigrams)."""

    name = "lexical"

    # 4096 dims keeps hash collisions (and thus spurious similarity between
    # unrelated texts) negligible, so out-of-scope queries score near zero.
    def __init__(self, dim: int = 4096) -> None:
        self.dimension = dim

    def _features(self, text: str) -> list[str]:
        tokens = [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]
        bigrams = [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
        return tokens + bigrams

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dimension, dtype=np.float32)
        for feat in self._features(text):
            digest = hashlib.md5(feat.encode("utf-8")).hexdigest()
            idx = int(digest, 16) % self.dimension
            vec[idx] += 1.0
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t).tolist() for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text).tolist()


class BgeEmbedder:
    """Real semantic embedder (BAAI/bge-m3) via sentence-transformers."""

    name = "bge-m3"

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "sentence-transformers is not installed. Install the real embedder "
                'with:  pip install -e ".[embeddings]"  — or set EMBED_MODEL=lexical '
                "to use the lightweight embedder on a low-config machine."
            ) from exc
        logger.info("Loading embedding model %s (first run downloads weights)…", model_name)
        self._model = SentenceTransformer(model_name)
        self.dimension = int(self._model.get_sentence_embedding_dimension())

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode([text], normalize_embeddings=True)[0].tolist()


def _use_lexical(settings: Settings) -> bool:
    model = settings.embed_model.strip().lower()
    return settings.is_stub or model in {"", "stub", "lexical"}


def get_embedder(settings: Settings) -> Embedder:
    """Select the embedder implementation for the current configuration."""
    if _use_lexical(settings):
        logger.info("Using LexicalEmbedder (lightweight, no model download).")
        return LexicalEmbedder()
    return BgeEmbedder(settings.embed_model)
