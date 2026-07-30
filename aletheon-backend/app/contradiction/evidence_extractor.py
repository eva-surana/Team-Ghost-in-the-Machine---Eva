"""
evidence_extractor.py — Extract the conflicting text fragments from a pair.

Only called on pairs that passed the scorer threshold — avoids wasteful
work on weak candidates.

Strategy:
  1. Compute the set difference of content words between claim_a and claim_b.
     Words unique to claim_a are the "conflicting fragment" of claim_a;
     words unique to claim_b are the conflicting fragment of claim_b.
  2. Find the contiguous spans in each text that contain those unique words
     and return a short excerpt (≤ 60 chars) centered on the first unique word.
  3. Also tag which feature drove the conflict:
       - "numeric_conflict"   if numeric_mismatch feature fired
       - "negation_conflict"  if negation_mismatch feature fired
       - "semantic_conflict"  otherwise

Complexity: O(w) where w = claim length in words.  Negligible.

Extractive: no LLM, no model inference — pure token set operations.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass

from app.contradiction.normalizer import NormalizedClaim

logger = logging.getLogger(__name__)

_STOP = frozenset([
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "that", "this", "these", "those", "its", "it",
])

_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?(?:%|million|billion|thousand)?\b", re.IGNORECASE)
_NEGATION = frozenset(["not", "no", "never", "neither", "nor", "cannot", "without", "none"])


@dataclass(frozen=True)
class ExtractedEvidence:
    conflict_type: str                   # "numeric_conflict" | "negation_conflict" | "semantic_conflict"
    fragment_a: str                      # conflicting excerpt from claim_a
    fragment_b: str                      # conflicting excerpt from claim_b
    unique_terms_a: list[str]            # content words unique to claim_a
    unique_terms_b: list[str]            # content words unique to claim_b


def extract_evidence(
    claim_a: NormalizedClaim,
    claim_b: NormalizedClaim,
    features: dict,
) -> ExtractedEvidence:
    """
    Extract the conflicting text fragments and classify the conflict type.

    Args:
        claim_a:  First normalized claim.
        claim_b:  Second normalized claim.
        features: Feature dict from classifier_bridge (numeric_mismatch, negation_mismatch, etc.)

    Returns:
        ExtractedEvidence with conflict_type, fragments, and unique terms.
    """
    text_a = claim_a.text.lower()
    text_b = claim_b.text.lower()

    words_a = {w for w in text_a.split() if w not in _STOP and len(w) > 2}
    words_b = {w for w in text_b.split() if w not in _STOP and len(w) > 2}

    unique_a = sorted(words_a - words_b)
    unique_b = sorted(words_b - words_a)

    # ── Conflict type classification ─────────────────────────────────────────
    if features.get("numeric_mismatch"):
        nums_a = _NUMBER_RE.findall(claim_a.text)
        nums_b = _NUMBER_RE.findall(claim_b.text)
        conflict_type = "numeric_conflict"
        # Numeric fragments: the numbers themselves
        fragment_a = ", ".join(nums_a[:3]) or _short_excerpt(claim_a.text, unique_a)
        fragment_b = ", ".join(nums_b[:3]) or _short_excerpt(claim_b.text, unique_b)
    elif features.get("negation_mismatch"):
        conflict_type = "negation_conflict"
        # Negation fragments: find the negation word and its context
        fragment_a = _negation_context(claim_a.text) or _short_excerpt(claim_a.text, unique_a)
        fragment_b = _negation_context(claim_b.text) or _short_excerpt(claim_b.text, unique_b)
    else:
        conflict_type = "semantic_conflict"
        fragment_a = _short_excerpt(claim_a.text, unique_a)
        fragment_b = _short_excerpt(claim_b.text, unique_b)

    return ExtractedEvidence(
        conflict_type=conflict_type,
        fragment_a=fragment_a[:120],
        fragment_b=fragment_b[:120],
        unique_terms_a=unique_a[:6],
        unique_terms_b=unique_b[:6],
    )


def _short_excerpt(text: str, anchors: list[str], window: int = 60) -> str:
    """Return a ≤window-char excerpt of text anchored on the first anchor word."""
    if not anchors:
        return text[:window]
    anchor = anchors[0]
    idx = text.lower().find(anchor)
    if idx < 0:
        return text[:window]
    start = max(0, idx - 20)
    return ("..." if start > 0 else "") + text[start:start + window]


def _negation_context(text: str, window: int = 50) -> str:
    """Return the context around the first negation word."""
    words = text.split()
    for i, w in enumerate(words):
        if w.lower() in _NEGATION:
            start = max(0, i - 2)
            end = min(len(words), i + 5)
            return " ".join(words[start:end])
    return ""
