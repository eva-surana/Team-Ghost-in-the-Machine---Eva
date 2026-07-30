"""
classifier_bridge.py — Exposes the contradiction probability from the
existing entailment classifier without adding any new model or inference call.

Design:
  The existing VerificationEngine calls classifier.predict_proba() and extracts
  only proba[2] (entailment). The contradiction probability at proba[0] is
  silently discarded. This bridge reuses the EXACT same code path
  (extract_features → predict_proba) and returns all three class probabilities.

  Label indices (match train_entailment_classifier.py LABEL_MAP):
      0 → contradicted
      1 → neutral
      2 → entailed

  Heuristic fallback (no classifier loaded):
      Uses negation_mismatch + low tfidf_cosine as contradiction signal.
      This matches the spirit of VerificationEngine._heuristic() but
      inverted: high negation_mismatch + low overlap → contradiction.

Reuse:
  - Same `extract_features` function from app.verification.feature_extractor
  - Same global TF-IDF vectorizer from ArtifactRegistry (already in memory)
  - No new model load, no new pickle, no new import beyond what already runs
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.models.registry import ArtifactRegistry
from app.verification.feature_extractor import extract_features

logger = logging.getLogger(__name__)

# Label indices — must match train_entailment_classifier.py LABEL_MAP
_IDX_CONTRADICTED = 0
_IDX_NEUTRAL      = 1
_IDX_ENTAILED     = 2


@dataclass(frozen=True)
class ClassificationResult:
    contradiction_prob: float    # P(contradicted)  ∈ [0, 1]
    neutral_prob: float          # P(neutral)        ∈ [0, 1]
    entailment_prob: float       # P(entailed)       ∈ [0, 1]
    features: dict               # raw feature dict for inspectability
    used_heuristic: bool         # True when classifier not loaded


class ContradictionClassifierBridge:
    """
    Wraps the existing entailment LogisticRegression to extract
    contradiction probability from the same predict_proba call.
    """

    def score_pair(
        self,
        text_a: str,
        text_b: str,
    ) -> ClassificationResult:
        """
        Score a (text_a, text_b) pair for contradiction.

        Uses extract_features(text_a, text_b, global_vectorizer) — the same
        feature extraction the verifier uses for claim→source pairs.
        The asymmetry (a vs b ordering) is intentional: for contradiction
        detection we also score (b, a) and take the max.

        Args:
            text_a: First claim text.
            text_b: Second claim text (the "source" for feature extraction).

        Returns:
            ClassificationResult with all three class probabilities.
        """
        reg = ArtifactRegistry.get()
        vectorizer = None
        classifier = None
        if reg.classifier_loaded and reg.classifier:
            vectorizer = reg.classifier.get("vectorizer")
            classifier = reg.classifier.get("classifier")

        # Forward direction: A as claim, B as source
        feat_vec, feat_dict = extract_features(text_a, text_b, vectorizer)

        if classifier is not None:
            result_fwd = self._classify(classifier, feat_vec, feat_dict)
            # Reverse direction: B as claim, A as source — captures asymmetric contradictions
            feat_vec_rev, feat_dict_rev = extract_features(text_b, text_a, vectorizer)
            result_rev = self._classify(classifier, feat_vec_rev, feat_dict_rev)
            # Take the direction with the higher contradiction probability
            if result_rev.contradiction_prob > result_fwd.contradiction_prob:
                return result_rev
            return result_fwd
        else:
            return self._heuristic(feat_dict)

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _classify(classifier, feat_vec: list[float], feat_dict: dict) -> ClassificationResult:
        X = np.array(feat_vec).reshape(1, -1)
        proba = classifier.predict_proba(X)[0]
        return ClassificationResult(
            contradiction_prob=float(proba[_IDX_CONTRADICTED]),
            neutral_prob=float(proba[_IDX_NEUTRAL]),
            entailment_prob=float(proba[_IDX_ENTAILED]),
            features=feat_dict,
            used_heuristic=False,
        )

    @staticmethod
    def _heuristic(feat_dict: dict) -> ClassificationResult:
        """
        Heuristic contradiction score when classifier is not loaded.
        Contradiction signal = negation mismatch OR numeric mismatch
                               AND moderate topical similarity.
        """
        tfidf_cos = feat_dict.get("tfidf_cosine", 0.0)
        negation  = feat_dict.get("negation_mismatch", 0.0)
        numeric   = feat_dict.get("numeric_mismatch", 0.0)

        # Requires some topical overlap (otherwise claims are just unrelated)
        relatedness = max(tfidf_cos, feat_dict.get("word_overlap", 0.0))
        contradiction_prob = relatedness * (0.6 * negation + 0.4 * numeric)
        entailment_prob = max(
            0.0,
            0.5 * tfidf_cos + 0.3 * feat_dict.get("word_overlap", 0.0)
            - 0.3 * negation - 0.2 * numeric,
        )
        neutral_prob = max(0.0, 1.0 - contradiction_prob - entailment_prob)
        # Renormalise
        total = contradiction_prob + neutral_prob + entailment_prob or 1.0
        return ClassificationResult(
            contradiction_prob=round(contradiction_prob / total, 4),
            neutral_prob=round(neutral_prob / total, 4),
            entailment_prob=round(entailment_prob / total, 4),
            features={**feat_dict, "_used_heuristic_fallback": True},
            used_heuristic=True,
        )


# Module-level singleton
classifier_bridge = ContradictionClassifierBridge()
