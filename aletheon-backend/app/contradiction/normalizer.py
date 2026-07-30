"""
normalizer.py — Claim text normalization and deduplication.

Responsibilities:
  - Strip leading bullets/numbers/punctuation (e.g. "1. ", "• ", "(a) ")
  - Collapse internal whitespace
  - Build a deduplicated list of (normalized_text, original_SourceSpan) pairs

Optimization:
  - O(n) single pass with a hash set for exact-duplicate detection.
  - Normalized text is used for candidate selection and classification;
    original span is preserved for source linking in the API response.
  - Does NOT lowercase for classification (feature_extractor does that
    internally). Normalization is limited to structural noise removal.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass

from app.models.schemas import SourceSpan

logger = logging.getLogger(__name__)

# Patterns that indicate structural noise at the start of a span
_LEADING_NOISE = re.compile(
    r"^(?:\s*(?:\d+[\.\)]\s+|\(?[a-z]\)\s+|[-•◦▪▸*]\s+))+",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class NormalizedClaim:
    text: str           # normalized text used for similarity/classification
    original: str       # raw original text for display
    source_span: SourceSpan
    claim_id: str       # derived from source_span.source_id


def normalize_spans(spans: list[SourceSpan]) -> list[NormalizedClaim]:
    """
    Normalize a list of SourceSpans into deduplicated NormalizedClaims.

    Deduplication is by exact normalized text — verbatim duplicates
    (e.g., repeated section headers) are dropped after the first occurrence.
    Spans shorter than 8 words are skipped (too short to carry a claim).

    Args:
        spans: Raw SourceSpans from job_manager.get_all_spans()

    Returns:
        Deduplicated list of NormalizedClaim, preserving document order.
    """
    seen: set[str] = set()
    result: list[NormalizedClaim] = []

    for span in spans:
        raw = span.text or ""
        # Strip structural leading noise
        cleaned = _LEADING_NOISE.sub("", raw).strip()
        # Collapse internal whitespace
        normalized = _WHITESPACE.sub(" ", cleaned)

        if not normalized:
            continue
        # Skip very short spans — unlikely to contain a falsifiable claim
        if len(normalized.split()) < 8:
            continue
        # Deduplicate by normalized form
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)

        result.append(NormalizedClaim(
            text=normalized,
            original=raw,
            source_span=span,
            claim_id=f"c_{span.source_id}",
        ))

    logger.debug(
        f"[Normalizer] {len(spans)} spans → {len(result)} unique normalized claims"
    )
    return result
