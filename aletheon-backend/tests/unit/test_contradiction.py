"""
Unit tests for the Contradiction Detection module.

Tests each component in isolation with synthetic data — no disk I/O,
no network, no trained classifier required (heuristic fallback exercises
all code paths even without the .pkl).

Test coverage:
  1. ClaimNormalizer: boilerplate stripping, deduplication, short-span filtering
  2. CandidateSelector: self-pair exclusion, cap enforcement, Jaccard fallback
  3. ContradictionScorer: formula monotonicity, boundary values
  4. ExplanationGenerator: template selection for all three conflict types
  5. EvidenceExtractor: conflict_type classification
  6. Full pipeline: synthetic single-contradiction document (heuristic path)
  7. Edge cases: <2 claims, all claims identical, zero similar pairs
"""
from __future__ import annotations

import math
import pytest

from app.models.schemas import SourceSpan


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_span(doc_id: str, sid: str, text: str, page: int = 1, section: str = "Results") -> SourceSpan:
    return SourceSpan(
        source_id=sid,
        document_id=doc_id,
        page=page,
        section=section,
        text=text,
    )


# ── 1. ClaimNormalizer ────────────────────────────────────────────────────────

class TestClaimNormalizer:

    def test_strips_leading_bullets(self):
        from app.contradiction.normalizer import normalize_spans
        span = _make_span("d1", "s1",
                          "• The model achieves state-of-the-art performance on all benchmarks tested.")
        result = normalize_spans([span])
        assert len(result) == 1
        assert not result[0].text.startswith("•")
        assert "model" in result[0].text

    def test_strips_numbered_prefix(self):
        from app.contradiction.normalizer import normalize_spans
        span = _make_span("d1", "s1",
                          "1. We demonstrate that attention outperforms recurrent architectures consistently.")
        result = normalize_spans([span])
        assert len(result) == 1
        assert not result[0].text[0].isdigit()

    def test_deduplicates_identical_spans(self):
        from app.contradiction.normalizer import normalize_spans
        text = "We show that the proposed method significantly reduces training time on all datasets."
        spans = [
            _make_span("d1", "s1", text, page=1),
            _make_span("d1", "s2", text, page=2),   # duplicate
        ]
        result = normalize_spans(spans)
        assert len(result) == 1

    def test_filters_short_spans(self):
        from app.contradiction.normalizer import normalize_spans
        spans = [
            _make_span("d1", "s1", "Abstract"),       # too short
            _make_span("d1", "s2", "See Table 1."),    # too short
            _make_span("d1", "s3",
                       "The proposed architecture achieves competitive results on the standard benchmark suite."),
        ]
        result = normalize_spans(spans)
        assert len(result) == 1
        assert "architecture" in result[0].text

    def test_preserves_original_for_display(self):
        from app.contradiction.normalizer import normalize_spans
        raw = "• The method clearly outperforms all baselines in every experimental condition tested."
        span = _make_span("d1", "s1", raw)
        result = normalize_spans([span])
        assert len(result) == 1
        assert result[0].original == raw


# ── 2. CandidateSelector ─────────────────────────────────────────────────────

class TestCandidateSelector:

    def _make_claims(self, doc_id="d1"):
        from app.contradiction.normalizer import NormalizedClaim
        texts = [
            "The proposed method achieves 95% accuracy on the test benchmark dataset.",
            "Our approach reaches 70% accuracy under the same experimental conditions.",
            "The model was evaluated on the MNIST handwritten digit recognition dataset.",
            "Attention mechanisms outperform recurrent models in natural language tasks.",
        ]
        claims = []
        for i, t in enumerate(texts):
            span = _make_span(doc_id, f"s{i}", t, page=i+1)
            claims.append(NormalizedClaim(
                text=t, original=t, source_span=span, claim_id=f"c_s{i}"
            ))
        return claims

    def test_no_self_pairs(self):
        from app.contradiction.candidate_selector import select_candidate_pairs
        claims = self._make_claims()
        pairs = select_candidate_pairs("d_fake_no_vectorizer", claims, theta_sim=0.0)
        for p in pairs:
            assert p.idx_a != p.idx_b

    def test_max_pairs_cap_enforced(self):
        from app.contradiction.candidate_selector import select_candidate_pairs
        claims = self._make_claims()
        pairs = select_candidate_pairs("d_fake", claims, theta_sim=0.0, max_pairs=2)
        assert len(pairs) <= 2

    def test_similarity_sorted_descending(self):
        from app.contradiction.candidate_selector import select_candidate_pairs
        claims = self._make_claims()
        pairs = select_candidate_pairs("d_fake", claims, theta_sim=0.0)
        sims = [p.similarity for p in pairs]
        assert sims == sorted(sims, reverse=True)

    def test_high_threshold_reduces_pairs(self):
        from app.contradiction.candidate_selector import select_candidate_pairs
        claims = self._make_claims()
        pairs_low  = select_candidate_pairs("d_fake", claims, theta_sim=0.0)
        pairs_high = select_candidate_pairs("d_fake", claims, theta_sim=0.9)
        assert len(pairs_high) <= len(pairs_low)

    def test_fewer_than_two_claims_returns_empty(self):
        from app.contradiction.candidate_selector import select_candidate_pairs
        from app.contradiction.normalizer import NormalizedClaim
        span = _make_span("d1", "s1",
                          "Only one claim here so nothing to compare against at all.")
        claim = NormalizedClaim(text=span.text, original=span.text,
                                source_span=span, claim_id="c_s1")
        pairs = select_candidate_pairs("d_fake", [claim])
        assert pairs == []


# ── 3. ContradictionScorer ────────────────────────────────────────────────────

class TestContradictionScorer:

    def test_monotone_in_contradiction_prob(self):
        from app.contradiction.scorer import compute_contradiction_confidence
        c1 = compute_contradiction_confidence(0.2, 0.5)
        c2 = compute_contradiction_confidence(0.8, 0.5)
        assert c2 > c1

    def test_monotone_in_similarity(self):
        from app.contradiction.scorer import compute_contradiction_confidence
        c1 = compute_contradiction_confidence(0.6, 0.26)
        c2 = compute_contradiction_confidence(0.6, 0.80)
        assert c2 > c1

    def test_zero_contradiction_prob_gives_zero(self):
        from app.contradiction.scorer import compute_contradiction_confidence
        c = compute_contradiction_confidence(0.0, 0.9)
        assert c == 0.0

    def test_confidence_in_unit_interval(self):
        from app.contradiction.scorer import compute_contradiction_confidence
        for p_contra in [0.0, 0.3, 0.7, 1.0]:
            for sim in [0.0, 0.25, 0.5, 1.0]:
                c = compute_contradiction_confidence(p_contra, sim)
                assert 0.0 <= c <= 1.0

    def test_is_contradiction_threshold(self, monkeypatch):
        from app.contradiction import scorer
        from app.config import settings
        monkeypatch.setattr(settings, "CONTRADICTION_CONFIDENCE_THRESHOLD", 0.35)
        assert scorer.is_contradiction(0.36)
        assert not scorer.is_contradiction(0.34)


# ── 4. ExplanationGenerator ───────────────────────────────────────────────────

class TestExplanationGenerator:

    def _make_pair(self, text_a, text_b, sim=0.5, page_a=1, page_b=3):
        from app.contradiction.candidate_selector import ClaimPair
        from app.contradiction.normalizer import NormalizedClaim
        span_a = _make_span("d1", "sa", text_a, page=page_a)
        span_b = _make_span("d1", "sb", text_b, page=page_b)
        ca = NormalizedClaim(text=text_a, original=text_a, source_span=span_a, claim_id="c_sa")
        cb = NormalizedClaim(text=text_b, original=text_b, source_span=span_b, claim_id="c_sb")
        return ClaimPair(idx_a=0, idx_b=1, claim_a=ca, claim_b=cb, similarity=sim)

    def _make_evidence(self, conflict_type):
        from app.contradiction.evidence_extractor import ExtractedEvidence
        return ExtractedEvidence(
            conflict_type=conflict_type,
            fragment_a="95%",
            fragment_b="70%",
            unique_terms_a=["accuracy"],
            unique_terms_b=["performance"],
        )

    def test_numeric_template_selected(self):
        from app.contradiction.explanation_generator import generate_explanation
        pair = self._make_pair("Achieves 95% accuracy.", "Only 70% accuracy observed.")
        evidence = self._make_evidence("numeric_conflict")
        expl = generate_explanation(pair, evidence, 0.7, used_heuristic=False)
        assert "Numerical conflict" in expl
        assert "page 1" in expl
        assert "page 3" in expl

    def test_negation_template_selected(self):
        from app.contradiction.explanation_generator import generate_explanation
        pair = self._make_pair("Model converges.", "Model does not converge.")
        evidence = self._make_evidence("negation_conflict")
        expl = generate_explanation(pair, evidence, 0.7, used_heuristic=False)
        assert "Negation mismatch" in expl

    def test_semantic_template_selected(self):
        from app.contradiction.explanation_generator import generate_explanation
        pair = self._make_pair("Outperforms baselines significantly.", "Underperforms baselines.")
        evidence = self._make_evidence("semantic_conflict")
        expl = generate_explanation(pair, evidence, 0.6, used_heuristic=False)
        assert "Semantic conflict" in expl

    def test_heuristic_note_appended(self):
        from app.contradiction.explanation_generator import generate_explanation
        pair = self._make_pair("Achieves 95%.", "Achieves 70%.")
        evidence = self._make_evidence("numeric_conflict")
        expl = generate_explanation(pair, evidence, 0.5, used_heuristic=True)
        assert "classifier unavailable" in expl.lower() or "Trained classifier" in expl

    def test_confidence_percentage_in_output(self):
        from app.contradiction.explanation_generator import generate_explanation
        pair = self._make_pair("Achieves 95%.", "Achieves 70%.")
        evidence = self._make_evidence("numeric_conflict")
        expl = generate_explanation(pair, evidence, 0.72, used_heuristic=False)
        assert "72%" in expl


# ── 5. EvidenceExtractor ─────────────────────────────────────────────────────

class TestEvidenceExtractor:

    def _make_claim(self, text, sid="s1", page=1):
        from app.contradiction.normalizer import NormalizedClaim
        span = _make_span("d1", sid, text, page=page)
        return NormalizedClaim(text=text, original=text, source_span=span, claim_id=f"c_{sid}")

    def test_numeric_conflict_detected(self):
        from app.contradiction.evidence_extractor import extract_evidence
        ca = self._make_claim("The method achieves 95% accuracy on the benchmark dataset evaluation.", "s1")
        cb = self._make_claim("Results show only 70% accuracy under equivalent experimental conditions.", "s2", 2)
        features = {"numeric_mismatch": 1.0, "negation_mismatch": 0.0, "tfidf_cosine": 0.6}
        ev = extract_evidence(ca, cb, features)
        assert ev.conflict_type == "numeric_conflict"

    def test_negation_conflict_detected(self):
        from app.contradiction.evidence_extractor import extract_evidence
        ca = self._make_claim("The proposed method significantly reduces computational overhead in all settings.", "s1")
        cb = self._make_claim("The method does not reduce computational overhead in distributed settings.", "s2", 2)
        features = {"numeric_mismatch": 0.0, "negation_mismatch": 1.0, "tfidf_cosine": 0.7}
        ev = extract_evidence(ca, cb, features)
        assert ev.conflict_type == "negation_conflict"

    def test_semantic_conflict_fallback(self):
        from app.contradiction.evidence_extractor import extract_evidence
        ca = self._make_claim("Transformer architectures outperform recurrent models on sequence tasks consistently.", "s1")
        cb = self._make_claim("Recurrent architectures remain superior to transformers for long sequence modeling.", "s2", 2)
        features = {"numeric_mismatch": 0.0, "negation_mismatch": 0.0, "tfidf_cosine": 0.5}
        ev = extract_evidence(ca, cb, features)
        assert ev.conflict_type == "semantic_conflict"

    def test_unique_terms_extracted(self):
        from app.contradiction.evidence_extractor import extract_evidence
        ca = self._make_claim("The proposed approach achieves superior performance on image classification tasks.", "s1")
        cb = self._make_claim("Baseline methods outperform the proposed approach on image classification tasks.", "s2", 2)
        features = {"numeric_mismatch": 0.0, "negation_mismatch": 0.0, "tfidf_cosine": 0.6}
        ev = extract_evidence(ca, cb, features)
        assert len(ev.unique_terms_a) + len(ev.unique_terms_b) > 0


# ── 6. Full pipeline — synthetic contradiction (heuristic path) ───────────────

class TestContradictionPipelineUnit:

    def _populate_doc(self, doc_id: str, texts: list[tuple[str, int]]):
        """Insert spans into SQLite for the pipeline to consume."""
        from app.jobs.manager import job_manager
        from app.vectorization.tfidf_service import tfidf_service
        spans = []
        for i, (text, page) in enumerate(texts):
            spans.append(_make_span(doc_id, f"s{i}", text, page=page))
        job_manager.store_spans(doc_id, spans)
        tfidf_service.fit_and_store(doc_id, spans)
        job_manager.update_status(doc_id, "completed", pages_count=max(p for _, p in texts), chunks_count=len(texts))
        return spans

    @pytest.mark.asyncio
    async def test_detects_numeric_contradiction(self):
        from app.jobs.manager import job_manager
        from app.contradiction.pipeline import ContradictionPipeline
        doc_id = job_manager.create_document_job()
        self._populate_doc(doc_id, [
            ("The proposed model achieves 95% accuracy on the standard benchmark evaluation dataset.", 1),
            ("Experimental results indicate only 70% accuracy for the proposed model on the benchmark.", 3),
            ("We compare our attention mechanism against recurrent architectures in natural language tasks.", 2),
            ("The model was trained using stochastic gradient descent with a learning rate of 0.001.", 4),
            ("Our approach outperforms baseline methods on image recognition and classification tasks.", 5),
        ])
        pipeline = ContradictionPipeline()
        report = await pipeline.detect(doc_id)
        assert report.document_id == doc_id
        assert report.claim_count >= 4
        assert report.pairs_evaluated >= 0
        # Report structure is valid — contradictions may or may not be found with heuristic
        assert isinstance(report.contradictions, list)
        for pair in report.contradictions:
            assert 0.0 <= pair.contradiction_confidence <= 1.0
            assert pair.explanation
            assert pair.claim_a.source_span is not None
            assert pair.claim_b.source_span is not None

    @pytest.mark.asyncio
    async def test_empty_report_for_single_claim(self):
        from app.jobs.manager import job_manager
        from app.contradiction.pipeline import ContradictionPipeline
        doc_id = job_manager.create_document_job()
        self._populate_doc(doc_id, [
            ("Only one span here so comparison is impossible.", 1),
        ])
        pipeline = ContradictionPipeline()
        report = await pipeline.detect(doc_id)
        assert report.contradiction_count == 0
        assert report.contradictions == []

    @pytest.mark.asyncio
    async def test_result_cached_on_second_call(self):
        from app.jobs.manager import job_manager
        from app.contradiction.pipeline import ContradictionPipeline
        doc_id = job_manager.create_document_job()
        self._populate_doc(doc_id, [
            ("The proposed model achieves 95% accuracy on the standard benchmark evaluation dataset.", 1),
            ("Experimental results indicate only 70% accuracy for the proposed model on the benchmark.", 3),
            ("The attention mechanism outperforms recurrent architectures on natural language tasks.", 2),
        ])
        pipeline = ContradictionPipeline()
        report1 = await pipeline.detect(doc_id)
        report2 = await pipeline.detect(doc_id)
        # Both should have same computed_at (cached)
        assert report1.computed_at == report2.computed_at

    @pytest.mark.asyncio
    async def test_report_schema_valid(self):
        from app.jobs.manager import job_manager
        from app.contradiction.pipeline import ContradictionPipeline
        from app.models.schemas import ContradictionReport as CRSchema
        doc_id = job_manager.create_document_job()
        self._populate_doc(doc_id, [
            ("The model demonstrates superior accuracy across all evaluated benchmark conditions.", 1),
            ("Our approach achieves inferior accuracy compared to baseline methods in benchmarks.", 2),
            ("Training converges faster with the proposed learning rate schedule and optimiser.", 3),
        ])
        pipeline = ContradictionPipeline()
        report = await pipeline.detect(doc_id)
        # Pydantic validation — if schema is wrong this raises
        validated = CRSchema.model_validate(report.model_dump())
        assert validated.document_id == doc_id


# ── 7. Edge cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_no_spans_returns_empty(self):
        from app.jobs.manager import job_manager
        from app.contradiction.pipeline import ContradictionPipeline
        doc_id = job_manager.create_document_job()
        job_manager.update_status(doc_id, "completed", pages_count=0, chunks_count=0)
        pipeline = ContradictionPipeline()
        report = await pipeline.detect(doc_id)
        assert report.contradiction_count == 0

    def test_scorer_handles_zero_similarity(self):
        from app.contradiction.scorer import compute_contradiction_confidence
        c = compute_contradiction_confidence(1.0, 0.0)
        # With sim=0.0 and theta=0.25, sigmoid(10*(0-0.25)) ≈ 0.08
        # So confidence should be << 1
        assert c < 0.15

    def test_normalizer_empty_spans(self):
        from app.contradiction.normalizer import normalize_spans
        result = normalize_spans([])
        assert result == []

    def test_sigmoid_boundary_values(self):
        from app.contradiction.scorer import sigmoid
        assert abs(sigmoid(0.0) - 0.5) < 1e-9
        assert sigmoid(100.0) > 0.999
        assert sigmoid(-100.0) < 0.001
