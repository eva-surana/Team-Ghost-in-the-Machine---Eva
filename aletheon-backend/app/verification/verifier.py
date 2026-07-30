"""
Verification Engine — self-trained statistical entailment classifier.

Architecture:
  - Loads classifier artifact (LogisticRegression + shared TfidfVectorizer)
    from ArtifactRegistry at startup.
  - At runtime: extract 6 lexical features from (claim, source) pair.
  - LogisticRegression.predict_proba() → entailment probability.
  - entailment_prob mapped to verdict via configurable thresholds.
  - Every result audit-logged to SQLite.

Fallback (when classifier not loaded):
  Uses a pure heuristic based on the same features (no model needed),
  which is intentionally weaker — the system should prompt the operator
  to run prepare_offline_bundle.py to train the real classifier.

Independence property:
  The verifier uses the same TF-IDF vectorizer as the classifier artifact,
  NOT the per-document vectorizer from the retrieval layer.
  This preserves the "independent checker" property: the verifier's
  vocabulary was learned from the training data, not from the same document
  being checked.

Known ceiling (documented per spec):
  LogisticRegression over lexical features catches obvious contradictions
  (numeric mismatch, negation flip, clearly unrelated text).
  It misses subtle scope errors or causal misrepresentation where the
  claim and source share vocabulary but differ in implication.
  A pretrained NLI model would perform better — but would violate the
  no-pretrained-weights constraint. This tradeoff is explicit.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional, Tuple

import numpy as np

from app.config import settings
from app.jobs.manager import job_manager
from app.models.registry import ArtifactRegistry
from app.models.schemas import SourceSpan
from app.verification.feature_extractor import extract_features

logger = logging.getLogger(__name__)

Verdict = str  # "verified" | "partially_supported" | "unsupported"

# Label indices in the trained classifier (matches LABEL_MAP in trainer)
_IDX_CONTRADICTED = 0
_IDX_NEUTRAL = 1
_IDX_ENTAILED = 2


class VerificationEngine:

    def verify(
        self,
        doc_id: str,
        claim_text: str,
        cited_spans: list[SourceSpan],
    ) -> Tuple[Verdict, float, Optional[dict]]:
        """
        Returns (verdict, entailment_score, feature_dict).
        entailment_score ∈ [0, 1].
        feature_dict is logged and returned for API transparency.
        """
        if not cited_spans:
            self._log(doc_id, claim_text, [], "unsupported", 0.0, {}, "No cited spans.")
            return "unsupported", 0.0, {}

        source_text = " ".join(s.text for s in cited_spans)
        reg = ArtifactRegistry.get()

        vectorizer = None
        classifier = None
        if reg.classifier_loaded and reg.classifier:
            vectorizer = reg.classifier.get("vectorizer")
            classifier = reg.classifier.get("classifier")

        feat_vec, feat_dict = extract_features(claim_text, source_text, vectorizer)

        if classifier is not None:
            score, verdict = self._classify(classifier, feat_vec)
        else:
            score, verdict = self._heuristic(feat_dict)
            feat_dict["_used_heuristic_fallback"] = True

        cited_ids = [s.source_id for s in cited_spans]
        self._log(doc_id, claim_text, cited_ids, verdict, score, feat_dict, "")
        return verdict, score, feat_dict

    # ── Classifier path ───────────────────────────────────────────────────────

    def _classify(self, classifier, feat_vec: list[float]) -> Tuple[float, Verdict]:
        X = np.array(feat_vec).reshape(1, -1)
        proba = classifier.predict_proba(X)[0]   # [contradicted, neutral, entailed]
        entail_prob = float(proba[_IDX_ENTAILED])
        verdict = self._threshold(entail_prob)
        return entail_prob, verdict

    # ── Heuristic fallback (no classifier loaded) ─────────────────────────────

    @staticmethod
    def _heuristic(feat_dict: dict) -> Tuple[float, Verdict]:
        """
        Simple weighted heuristic when the trained classifier is absent.
        Uses the same features — inspectable and deterministic.
        """
        score = (
            0.5 * feat_dict.get("tfidf_cosine", 0.0) +
            0.3 * feat_dict.get("word_overlap", 0.0) +
            0.2 * feat_dict.get("bigram_overlap", 0.0)
        )
        # Hard penalties
        if feat_dict.get("numeric_mismatch"):
            score *= 0.4
        if feat_dict.get("negation_mismatch"):
            score *= 0.5
        verdict = VerificationEngine._threshold(score)
        return score, verdict

    @staticmethod
    def _threshold(score: float) -> Verdict:
        if score >= settings.ENTAILMENT_VERIFIED_THRESHOLD:
            return "verified"
        if score >= settings.ENTAILMENT_PARTIAL_THRESHOLD:
            return "partially_supported"
        return "unsupported"

    # ── Audit log ─────────────────────────────────────────────────────────────

    def _log(self, doc_id, claim_text, cited_ids, verdict, score, features, rationale):
        try:
            import json
            job_manager.log_verification(
                record_id=str(uuid.uuid4()),
                doc_id=doc_id,
                claim_text=claim_text,
                cited_source_ids=cited_ids,
                verdict=verdict,
                nli_score=score,
                rationale=rationale or str(features),
            )
        except Exception as exc:
            logger.debug(f"[Verifier] Audit log failed: {exc}")


verifier_engine = VerificationEngine()
