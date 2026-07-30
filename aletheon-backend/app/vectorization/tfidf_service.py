"""
TF-IDF Vectorization Service

Replaces the sentence-transformers / FAISS embedding pipeline entirely.

Design:
  - One TfidfVectorizer is fitted PER DOCUMENT at ingestion time.
    This is the "training" for this component: it learns vocabulary
    and IDF weights from the document's own chunks. No weights are
    downloaded or pre-learned.
  - The fitted vectorizer and the resulting sparse matrix are saved:
      data/doc_vectorizers/{doc_id}.pkl   ← the fitted vectorizer
      data/sparse_vectors/{doc_id}.npz    ← the sparse chunk matrix
  - At query time, the vectorizer is loaded from disk and used to
    transform the query string into the same TF-IDF space.
  - Retrieval is cosine_similarity(query_vec, chunk_matrix) — no FAISS.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.models.schemas import SourceSpan

logger = logging.getLogger(__name__)


def _vectorizer_path(doc_id: str) -> Path:
    d = settings.resolve_path(settings.DOC_VECTORIZERS_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{doc_id}.pkl"


def _matrix_path(doc_id: str) -> Path:
    d = settings.resolve_path(settings.SPARSE_VECTORS_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{doc_id}.npz"


class TFIDFService:
    """
    Fits and persists a per-document TF-IDF vectorizer.
    No pretrained weights. Vocabulary + IDF learned from document text at ingestion.
    """

    def fit_and_store(self, doc_id: str, spans: List[SourceSpan]) -> None:
        """
        Fit TfidfVectorizer over all span texts in this document.
        Persist vectorizer (.pkl) and sparse matrix (.npz).
        """
        if not spans:
            logger.warning(f"[TFIDFService] No spans for doc {doc_id} — skipping fit")
            return

        texts = [s.text for s in spans]
        vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),       # unigrams + bigrams
            max_features=20_000,
            sublinear_tf=True,        # log(1+tf) scaling
            min_df=1,
            strip_accents="unicode",
            lowercase=True,
        )

        try:
            matrix = vectorizer.fit_transform(texts)   # (N, vocab) sparse matrix

            # Persist vectorizer
            with open(_vectorizer_path(doc_id), "wb") as f:
                pickle.dump(vectorizer, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Persist sparse matrix
            sp.save_npz(str(_matrix_path(doc_id)), matrix)

            logger.debug(
                f"[TFIDFService] doc={doc_id}: {len(spans)} spans, "
                f"vocab={len(vectorizer.vocabulary_)}, matrix={matrix.shape}"
            )
        except Exception as exc:
            logger.error(f"[TFIDFService] fit_and_store failed for doc {doc_id}: {exc}")
            raise

    def vectorize_query(self, doc_id: str, query: str) -> Optional[sp.csr_matrix]:
        """
        Transform a query string using the document's fitted vectorizer.
        Returns a (1, vocab) sparse matrix, or None if vectorizer not found.
        """
        vpath = _vectorizer_path(doc_id)
        if not vpath.exists():
            return None
        try:
            with open(vpath, "rb") as f:
                vectorizer: TfidfVectorizer = pickle.load(f)
            return vectorizer.transform([query])
        except Exception as exc:
            logger.error(f"[TFIDFService] vectorize_query failed for doc {doc_id}: {exc}")
            return None

    def load_matrix(self, doc_id: str) -> Optional[sp.csr_matrix]:
        """Load the persisted sparse chunk matrix for a document."""
        mpath = _matrix_path(doc_id)
        if not mpath.exists():
            return None
        try:
            return sp.load_npz(str(mpath))
        except Exception as exc:
            logger.error(f"[TFIDFService] load_matrix failed for doc {doc_id}: {exc}")
            return None

    def load_vectorizer(self, doc_id: str) -> Optional[TfidfVectorizer]:
        vpath = _vectorizer_path(doc_id)
        if not vpath.exists():
            return None
        with open(vpath, "rb") as f:
            return pickle.load(f)

    def has_index(self, doc_id: str) -> bool:
        return _vectorizer_path(doc_id).exists() and _matrix_path(doc_id).exists()


# Module-level singleton
tfidf_service = TFIDFService()
