"""
Sparse retrieval layer — replaces FAISS dense-embedding search.

Uses cosine_similarity(query_vec, chunk_matrix) over scipy sparse
TF-IDF vectors.  No dense embeddings, no pretrained model.

The vectorizer and matrix are loaded from disk (written by TFIDFService
at ingestion time) and cached in-process per document.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import List, NamedTuple, Optional

import numpy as np
import scipy.sparse as sp
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.models.schemas import SourceSpan
from app.vectorization.tfidf_service import tfidf_service

logger = logging.getLogger(__name__)


class SearchResult(NamedTuple):
    span: SourceSpan
    score: float   # cosine similarity in [0, 1]


def _db_path() -> Path:
    return settings.resolve_path(settings.SQLITE_DB_PATH)


class SparseRetriever:
    """
    Cosine similarity retrieval over per-document TF-IDF sparse matrices.
    Matrices and vectorizers are loaded lazily and cached per-process.
    """

    def __init__(self) -> None:
        self._matrices: dict[str, sp.csr_matrix] = {}   # doc_id → sparse matrix

    def search(
        self, doc_id: str, query: str, top_k: Optional[int] = None
    ) -> List[SearchResult]:
        top_k = top_k or settings.RETRIEVAL_TOP_K

        # Load or retrieve cached sparse matrix
        matrix = self._load_matrix(doc_id)
        if matrix is None or matrix.shape[0] == 0:
            logger.warning(f"[Retriever] No TF-IDF matrix for doc {doc_id}")
            return []

        # Transform query into the same TF-IDF space
        q_vec = tfidf_service.vectorize_query(doc_id, query)
        if q_vec is None:
            logger.warning(f"[Retriever] No vectorizer for doc {doc_id}")
            return []

        # Cosine similarity: (1, vocab) × (N, vocab)^T → (1, N)
        sims = cosine_similarity(q_vec, matrix).flatten()

        # Fetch spans from SQLite (ordered consistently with matrix rows)
        spans = self._fetch_spans(doc_id)
        if len(spans) != matrix.shape[0]:
            logger.warning(
                f"[Retriever] span count {len(spans)} != matrix rows {matrix.shape[0]} "
                f"for doc {doc_id}. Using min."
            )
            n = min(len(spans), matrix.shape[0], len(sims))
            spans = spans[:n]
            sims = sims[:n]

        n_results = min(top_k, len(spans))
        top_idx = np.argsort(sims)[::-1][:n_results]
        return [
            SearchResult(span=spans[i], score=float(max(0.0, sims[i])))
            for i in top_idx
        ]

    def _load_matrix(self, doc_id: str) -> Optional[sp.csr_matrix]:
        if doc_id in self._matrices:
            return self._matrices[doc_id]
        matrix = tfidf_service.load_matrix(doc_id)
        if matrix is not None:
            self._matrices[doc_id] = matrix
        return matrix

    def _fetch_spans(self, doc_id: str) -> List[SourceSpan]:
        """Pull spans from SQLite in the same order they were inserted at ingestion."""
        try:
            con = sqlite3.connect(str(_db_path()), check_same_thread=False)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM spans WHERE document_id=? ORDER BY page, paragraph_offset",
                (doc_id,),
            ).fetchall()
            con.close()
            return [
                SourceSpan(
                    source_id=r["source_id"],
                    document_id=r["document_id"],
                    page=r["page"],
                    section=r["section"],
                    paragraph_offset=r["paragraph_offset"] or 0,
                    text=r["text"],
                )
                for r in rows
            ]
        except Exception as exc:
            logger.error(f"[Retriever] SQLite fetch failed: {exc}")
            return []


# Module-level singleton
sparse_retriever = SparseRetriever()
