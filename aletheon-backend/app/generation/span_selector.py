"""
Section-weighted span ranker for extractive generation.

Each extraction task (problem, gap, method, contribution, q&a) has a
different set of preferred document sections.  Spans from preferred
sections get a positional boost applied to their retrieval score.

This is entirely rule-based: no learned weights, no pretrained model.
The section → task mapping is documented here so it is inspectable.

Output: a ranked list of (SearchResult, boosted_score) sorted by
boosted_score descending.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from app.retrieval.sparse_store import SearchResult

# ── Section → task affinity map ───────────────────────────────────────────────
# Values: multiplier applied to the retrieval cosine score.
# 1.0 = neutral; >1.0 = prefer; <1.0 = penalise.

_SECTION_WEIGHTS: dict[str, dict[str, float]] = {
    "problem": {
        "abstract": 1.8,
        "introduction": 1.6,
        "motivation": 1.5,
        "background": 1.2,
        "related work": 1.0,
        "method": 0.6,
        "result": 0.5,
        "conclusion": 0.7,
    },
    "gap": {
        "abstract": 1.5,
        "introduction": 1.6,
        "related work": 1.8,
        "background": 1.4,
        "limitation": 1.3,
        "discussion": 1.2,
        "method": 0.7,
        "result": 0.6,
    },
    "method": {
        "method": 1.8,
        "approach": 1.8,
        "proposed": 1.7,
        "model": 1.5,
        "architecture": 1.6,
        "experiment": 1.2,
        "abstract": 1.0,
        "result": 0.8,
        "introduction": 0.7,
    },
    "contribution": {
        "conclusion": 1.8,
        "abstract": 1.5,
        "result": 1.7,
        "discussion": 1.4,
        "contribution": 1.9,
        "experiment": 1.3,
        "introduction": 1.0,
        "method": 0.8,
    },
    "qa": {
        # For Q&A all sections are treated equally; query term match drives ranking
    },
}

# Fallback section weight used when a section name doesn't match any key
_DEFAULT_WEIGHT = 1.0


def _section_weight(section: str | None, task: str) -> float:
    """Return the section-affinity multiplier for a given task."""
    if not section:
        return _DEFAULT_WEIGHT
    weights = _SECTION_WEIGHTS.get(task, {})
    section_lower = section.lower()
    for key, w in weights.items():
        if key in section_lower:
            return w
    return _DEFAULT_WEIGHT


def rank_spans(
    results: List[SearchResult],
    task: str,
    top_k: int = 5,
) -> List[Tuple[SearchResult, float]]:
    """
    Apply section-affinity weights to retrieval scores and re-rank.

    Returns: list of (SearchResult, boosted_score) sorted by boosted_score desc.
    """
    scored: List[Tuple[SearchResult, float]] = []
    for r in results:
        w = _section_weight(r.span.section, task)
        boosted = min(1.0, r.score * w)
        scored.append((r, boosted))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
