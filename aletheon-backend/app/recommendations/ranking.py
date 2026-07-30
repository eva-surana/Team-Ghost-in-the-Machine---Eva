"""
ranking.py — Local re-ranking of external API candidates.

Uses TF-IDF cosine similarity, consistent with the core pipeline's
retrieval strategy. No downloaded embedding model. No pretrained weights.

The "source paper profile" is built from its already-extracted
Research DNA fields (stored in SQLite by the core pipeline), plus
the full span text. These are read via the shared job_manager
data layer — no imports from ingestion/, retrieval/, or generation/.

Why rank locally?
  External APIs return papers in their own relevance order, which
  may differ from what is most similar to this specific paper.
  Local re-ranking keeps the "why recommended" story consistent
  with the evidence-first framing of the rest of the product.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

if TYPE_CHECKING:
    from app.recommendations.client import CandidatePaper


def _extract_key_terms(text: str, top_n: int = 8) -> list[str]:
    """
    Extract the top-n most informative unigrams/bigrams from text
    using a fast TF-IDF over single sentences.
    """
    if not text.strip():
        return []
    sentences = re.split(r"[.!?]\s+", text)
    if len(sentences) < 2:
        # Single-sentence text: split by comma/semicolon
        sentences = [text]
    try:
        vect = TfidfVectorizer(ngram_range=(1, 2), max_features=200,
                               stop_words="english", sublinear_tf=True)
        vect.fit(sentences)
        terms = sorted(vect.vocabulary_.keys(),
                       key=lambda t: vect.idf_[vect.vocabulary_[t]],
                       reverse=False)[:top_n]
        return terms
    except Exception:
        return []


def _shared_concepts(profile_text: str, candidate_abstract: str, top_n: int = 3) -> list[str]:
    """
    Find top-n concept terms that appear in both the profile and the candidate abstract.
    Returns a human-readable "why recommended" hint.
    """
    profile_words = set(re.findall(r"\b[a-z]{4,}\b", profile_text.lower()))
    abstract_words = set(re.findall(r"\b[a-z]{4,}\b", candidate_abstract.lower()))
    _STOPWORDS = {"that", "this", "with", "from", "have", "been", "they",
                  "also", "which", "their", "more", "than", "when", "into",
                  "than", "both", "only", "about", "over", "such", "some"}
    shared = (profile_words & abstract_words) - _STOPWORDS
    return sorted(shared)[:top_n]


def rank_candidates(
    profile_text: str,
    candidates: list["CandidatePaper"],
    top_k: int = 8,
) -> list[dict]:
    """
    Rank candidates by TF-IDF cosine similarity to the paper profile.

    Returns a list of dicts with the ranked candidates + similarity scores
    + shared_concepts, ready to be serialised into the API response.
    No network calls made here.
    """
    if not candidates:
        return []

    # Build corpus: [profile] + [candidate abstracts]
    corpus = [profile_text] + [
        f"{c.title} {c.abstract}" for c in candidates
    ]

    try:
        vect = TfidfVectorizer(ngram_range=(1, 2), max_features=5000,
                               sublinear_tf=True, stop_words="english")
        matrix = vect.fit_transform(corpus)
        profile_vec = matrix[0]
        candidate_vecs = matrix[1:]
        sims = cosine_similarity(profile_vec, candidate_vecs).flatten()
    except Exception:
        # If vectorisation fails (e.g., empty corpus), return unsorted list
        sims = [0.0] * len(candidates)

    ranked = sorted(zip(sims, candidates), key=lambda x: x[0], reverse=True)

    results = []
    for score, cand in ranked[:top_k]:
        abstract_snippet = (cand.abstract or "")[:300]
        shared = _shared_concepts(profile_text, cand.abstract)
        results.append({
            "title": cand.title,
            "authors": cand.authors[:5],   # cap for API response size
            "year": cand.year,
            "abstract_snippet": abstract_snippet,
            "source": cand.source,
            "url": cand.url,
            "similarity_score": round(float(score), 4),
            "shared_concepts": shared,
        })
    return results


def build_profile_text(doc_id: str) -> str:
    """
    Build a search-profile text for the paper from already-ingested data.
    Reads from the shared data layer (job_manager) — no core pipeline imports.
    """
    # Import here (not at module level) to keep the dependency graph clean
    from app.jobs.manager import job_manager

    parts: list[str] = []

    # Research DNA fields (if already computed)
    dna_data = job_manager.get_research_dna(doc_id)
    if dna_data:
        for field in ("problem", "gap", "method", "contribution"):
            claim = dna_data.get(field, {})
            text = claim.get("text", "")
            if text and not text.startswith("[No relevant"):
                parts.append(text[:300])

    # Top spans from the document (first 5 for efficiency)
    if not parts:
        spans = job_manager.get_all_spans(doc_id)
        for span in spans[:5]:
            if span.text and len(span.text) > 30:
                parts.append(span.text[:200])

    return " ".join(parts)
