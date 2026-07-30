"""
explanation_generator.py — Natural-language explanation of a detected contradiction.

Only called on pairs that passed the scorer threshold (CONTRADICTION_CONFIDENCE_THRESHOLD).
This gate prevents explanation work on weak candidates.

Design: Three deterministic feature-driven templates — no LLM, no model inference.

Template selection:
  1. numeric_conflict  → "Claim A states {nums_a} while Claim B states {nums_b}."
  2. negation_conflict → "Claim A asserts the positive while Claim B contains a negation."
  3. semantic_conflict → "These claims are topically related (similarity: X%) but their
                          content diverges on the following terms: {terms}."

All templates include:
  - Source page references for both claims
  - The similarity score
  - The contradiction confidence
  - A "known ceiling" note when the heuristic fallback was used

Complexity: O(1) — template string formatting only.
Deterministic: same inputs always produce the same explanation.
"""
from __future__ import annotations

import logging

from app.contradiction.candidate_selector import ClaimPair
from app.contradiction.evidence_extractor import ExtractedEvidence

logger = logging.getLogger(__name__)

# Known ceiling note appended when the trained classifier was not available
_HEURISTIC_NOTE = (
    " [Note: Trained classifier unavailable — explanation based on "
    "lexical heuristics. Run prepare_offline_bundle.py to train the classifier.]"
)


def generate_explanation(
    pair: ClaimPair,
    evidence: ExtractedEvidence,
    contradiction_confidence: float,
    used_heuristic: bool,
) -> str:
    """
    Generate a natural-language explanation for a detected contradiction.

    Args:
        pair:                   The ClaimPair (carries similarity, source spans).
        evidence:               ExtractedEvidence with conflict_type and fragments.
        contradiction_confidence: Final scorer output ∈ [0, 1].
        used_heuristic:         True if the trained classifier was not available.

    Returns:
        A single human-readable explanation string.
    """
    page_a = pair.claim_a.source_span.page
    page_b = pair.claim_b.source_span.page
    sim_pct = f"{pair.similarity:.0%}"
    conf_pct = f"{contradiction_confidence:.0%}"

    if evidence.conflict_type == "numeric_conflict":
        explanation = (
            f"Numerical conflict detected (confidence: {conf_pct}, "
            f"similarity: {sim_pct}). "
            f"Claim on page {page_a} states '{evidence.fragment_a}' "
            f"while the claim on page {page_b} states '{evidence.fragment_b}'. "
            f"These figures are not reconciled in the surrounding context."
        )

    elif evidence.conflict_type == "negation_conflict":
        explanation = (
            f"Negation mismatch detected (confidence: {conf_pct}, "
            f"similarity: {sim_pct}). "
            f"Claim on page {page_a} contains the phrase '{evidence.fragment_a}' "
            f"while the claim on page {page_b} contains '{evidence.fragment_b}'. "
            f"One asserts the positive and the other contains an explicit negation "
            f"on topically related content."
        )

    else:   # semantic_conflict
        terms_a = ", ".join(f"'{t}'" for t in evidence.unique_terms_a[:4])
        terms_b = ", ".join(f"'{t}'" for t in evidence.unique_terms_b[:4])
        terms_note = ""
        if terms_a and terms_b:
            terms_note = (
                f" Key terms unique to claim A: {terms_a}. "
                f"Key terms unique to claim B: {terms_b}."
            )
        explanation = (
            f"Semantic conflict detected (confidence: {conf_pct}, "
            f"similarity: {sim_pct}). "
            f"Claim on page {page_a} and claim on page {page_b} are "
            f"topically related but their content diverges.{terms_note}"
        )

    if used_heuristic:
        explanation += _HEURISTIC_NOTE

    return explanation
