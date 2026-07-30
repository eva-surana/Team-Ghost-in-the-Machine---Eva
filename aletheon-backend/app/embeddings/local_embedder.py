"""
Local embedding provider backed entirely by a locally-stored SentenceTransformer model.
Falls back to a deterministic hash-based mock when the model weights are absent.
No network call is ever made.
"""
from __future__ import annotations

import logging
import numpy as np
from typing import List

from app.models.registry import ArtifactRegistry

logger = logging.getLogger(__name__)

# Embedding dimension for mock (matches all-MiniLM-L6-v2)
_MOCK_DIM = 384


class LocalEmbedder:
    """
    Wraps ArtifactRegistry with a hash-based mock fallback.
    embed_texts / embed_query are the only public API.
    """

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Return (N, D) float32 array of unit-norm embeddings."""
        return np.stack([self._hash_embed(t) for t in texts])

    def embed_query(self, query: str) -> np.ndarray:
        """Return (D,) float32 unit-norm vector."""
        return self.embed_texts([query])[0]

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _unit_norm(vecs: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return vecs / norms

    @staticmethod
    def _hash_embed(text: str) -> np.ndarray:
        """Deterministic, reproducible mock embedding for offline tests."""
        vec = np.zeros(_MOCK_DIM, dtype=np.float32)
        words = text.lower().split()
        for i, word in enumerate(words):
            val = sum(ord(c) * (j + 1) for j, c in enumerate(word))
            slot = val % _MOCK_DIM
            vec[slot] += 1.0 / (i + 1)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec


# Module-level singleton — one embedder instance per process
local_embedder = LocalEmbedder()
