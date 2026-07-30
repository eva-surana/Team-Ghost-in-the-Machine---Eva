"""
scorer.py — Contradiction confidence scoring.

Formula:
    contradiction_confidence = P(contradicted) × sim_weight(similarity)

    where sim_weight(s) = sigmoid(10 × (s − θ_sim))
                        = 1 / (1 + exp(−10(s − θ_sim)))

Rationale:
  - Pairs that barely pass the similarity threshold (s ≈ θ_sim) receive
    a low sim_weight (≈ 0.5), reducing their final score even if the
    classifier is uncertain.
  - Pairs with high similarity (s ≥ 0.6) receive sim_weight ≈ 1.0,
    so their score is dominated by the classifier's contradiction probability.
  - This avoids a hard cutoff at θ_sim and provides a smooth, monotone
    function in both P(contradicted) and similarity.

Threshold:
  CONTRADICTION_CONFIDENCE_THRESHOLD (default 0.35, configurable in .env)
  Pairs below this are discarded before evidence extraction and explanation.
  This keeps the pipeline's expensive later stages (evidence, explanation)
  from running on weak candidates.

Complexity:
  O(K) where K = len(pairs), purely arithmetic, negligible runtime.
"""
from __future__ import annotations

import math
import logging

from app.config import settings
from app.contradiction.candidate_selector import ClaimPair
from app.contradiction.classifier_bridge import ClassificationResult

logger = logging.getLogger(__name__)


def sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    # Alternative form for negative x avoids exp overflow
    e = math.exp(x)
    return e / (1.0 + e)


def compute_contradiction_confidence(
    contradiction_prob: float,
    similarity: float,
    theta_sim: float | None = None,
) -> float:
    """
    Compute the final contradiction_confidence ∈ [0, 1].

    Args:
        contradiction_prob: P(contradicted) from classifier_bridge.
        similarity:         TF-IDF cosine similarity from candidate_selector.
        theta_sim:          Similarity threshold used during candidate selection.

    Returns:
        contradiction_confidence ∈ [0, 1]
    """
    if theta_sim is None:
        theta_sim = settings.CONTRADICTION_SIMILARITY_THRESHOLD
    sim_weight = sigmoid(10.0 * (similarity - theta_sim))
    confidence = contradiction_prob * sim_weight
    return round(min(1.0, max(0.0, confidence)), 4)


def is_contradiction(confidence: float, threshold: float | None = None) -> bool:
    """True if confidence meets the reporting threshold."""
    if threshold is None:
        threshold = settings.CONTRADICTION_CONFIDENCE_THRESHOLD
    return confidence >= threshold
