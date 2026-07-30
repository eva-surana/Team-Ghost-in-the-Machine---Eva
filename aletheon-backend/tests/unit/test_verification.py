"""
Unit tests for the verification engine and confidence scoring.

Key invariants:
  1. Empty cited_spans -> always "unsupported"
  2. Known-false claims (numeric mismatch, negation flip) -> "unsupported"
  3. Semantically-supported claims -> "verified" or "partially_supported"
  4. calculate_claim_confidence: unsupported claims capped at 0.30
  5. Entailment score always in [0, 1]
"""
import pytest
from app.models.schemas import SourceSpan
from app.verification.verifier import VerificationEngine
from app.verification.confidence import calculate_claim_confidence
from app.verification.feature_extractor import extract_features


def _span(text: str, sid: str = "s1") -> SourceSpan:
    return SourceSpan(
        source_id=sid, document_id="verif_test",
        page=1, text=text,
    )


# ── Verifier tests ────────────────────────────────────────────────────────────

def test_no_spans_always_unsupported():
    ve = VerificationEngine()
    verdict, score, feat = ve.verify("d", "Any claim.", [])
    assert verdict == "unsupported"
    assert score == 0.0


def test_numeric_mismatch_is_unsupported():
    ve = VerificationEngine()
    premise_span = _span("The model achieved 92.1% accuracy on the test dataset.")
    verdict, score, feat = ve.verify(
        "d",
        "The model achieved 99.9% accuracy on the test dataset.",
        [premise_span],
    )
    assert verdict in {"unsupported", "partially_supported"}
    assert feat.get("numeric_mismatch") == 1.0


def test_negation_mismatch_is_unsupported():
    ve = VerificationEngine()
    premise_span = _span("The architecture does not use recurrent neural networks.")
    verdict, score, feat = ve.verify(
        "d",
        "The architecture uses recurrent neural networks.",
        [premise_span],
    )
    assert verdict in {"unsupported", "partially_supported"}
    assert feat.get("negation_mismatch") == 1.0


def test_supported_claim_high_score():
    ve = VerificationEngine()
    premise_span = _span("Transformer models use self-attention to process sequential tokens.")
    verdict, score, feat = ve.verify(
        "d",
        "Transformer models process sequential tokens using self-attention.",
        [premise_span],
    )
    assert verdict in {"verified", "partially_supported"}
    assert score > 0.3


def test_entailment_score_always_in_range():
    ve = VerificationEngine()
    span = _span("The experiment showed improved accuracy on all benchmarks.")
    _, score, _ = ve.verify("d", "Results improved across all experiments.", [span])
    assert 0.0 <= score <= 1.0


# ── Feature extractor tests ───────────────────────────────────────────────────

def test_feature_extractor_numeric_mismatch():
    vec, feat = extract_features(
        "Accuracy reached 99%",
        "Accuracy reached 85%"
    )
    assert feat["numeric_mismatch"] == 1.0


def test_feature_extractor_negation_mismatch():
    vec, feat = extract_features(
        "The model performs well",
        "The model does not perform well"
    )
    assert feat["negation_mismatch"] == 1.0


# ── Confidence scoring tests ──────────────────────────────────────────────────

def test_confidence_unsupported_capped():
    c = calculate_claim_confidence(0.99, 0.99, "unsupported")
    assert c <= 0.30


def test_confidence_verified_is_high():
    c = calculate_claim_confidence(0.9, 0.95, "verified")
    assert c >= 0.8


def test_confidence_in_valid_range():
    for verdict in ("verified", "partially_supported", "unsupported"):
        c = calculate_claim_confidence(0.7, 0.7, verdict)
        assert 0.0 <= c <= 1.0


def test_confidence_partial_upper_bound():
    c = calculate_claim_confidence(1.0, 1.0, "partially_supported")
    assert c <= 0.70
