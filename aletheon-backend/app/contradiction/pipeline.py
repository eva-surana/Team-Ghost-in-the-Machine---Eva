"""
pipeline.py — End-to-end contradiction detection orchestrator.

Composes all components and implements the lazy-cache pattern
matching the existing get_dependency_graph / get_research_dna endpoints.

Cache key: "contradictions" in the doc_artifacts SQLite table.
First call: run full pipeline, persist result.
Subsequent calls: return cached ContradictionReport immediately.

Pipeline sequence:
  1. Load spans from job_manager
  2. Normalize → deduplicated NormalizedClaim list
  3. Candidate selection (similarity threshold + top-K cap)
  4. For each candidate pair:
       a. ClassifierBridge.score_pair()
       b. ContradictionScorer.compute_confidence()
       c. [if confidence ≥ threshold] EvidenceExtractor.extract()
       d. [if confidence ≥ threshold] ExplanationGenerator.explain()
  5. Collect ContradictionPair objects above threshold
  6. Persist ContradictionReport to SQLite
  7. Return ContradictionReport

Logging:
  - INFO  for pipeline start/end (includes claim count, pair counts, timings)
  - DEBUG for per-pair classifier scores
  - WARNING for missing vectorizer (uses Jaccard fallback)
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.contradiction.candidate_selector import select_candidate_pairs
from app.contradiction.classifier_bridge import classifier_bridge
from app.contradiction.evidence_extractor import extract_evidence
from app.contradiction.explanation_generator import generate_explanation
from app.contradiction.normalizer import normalize_spans
from app.contradiction.scorer import compute_contradiction_confidence, is_contradiction
from app.jobs.manager import job_manager
from app.models.schemas import (
    ConflictingFragment,
    ContradictionPair,
    ContradictionReport,
    SourceSpan,
)

logger = logging.getLogger(__name__)

_CACHE_KEY = "contradictions"


class ContradictionPipeline:
    """
    Orchestrates within-paper contradiction detection.

    Usage:
        report = await contradiction_pipeline.detect(doc_id)
    """

    async def detect(self, doc_id: str) -> ContradictionReport:
        """
        Detect within-paper contradictions for the given document.

        Returns a cached ContradictionReport if already computed.
        Otherwise runs the full pipeline and caches the result.
        """
        # ── Cache check ───────────────────────────────────────────────────────
        cached = job_manager.get_artifact(doc_id, _CACHE_KEY)
        if cached:
            logger.debug(f"[ContradictionPipeline] Serving cached result for doc={doc_id}")
            return ContradictionReport.model_validate(cached)

        t0 = time.perf_counter()
        logger.info(f"[ContradictionPipeline] Starting detection for doc={doc_id}")

        # ── Step 1: Load spans ────────────────────────────────────────────────
        spans = job_manager.get_all_spans(doc_id)
        if not spans:
            return self._empty_report(doc_id, claim_count=0, pairs_evaluated=0)

        # ── Step 2: Normalize ─────────────────────────────────────────────────
        claims = normalize_spans(spans)
        if len(claims) < 2:
            return self._empty_report(doc_id, claim_count=len(claims), pairs_evaluated=0)

        # ── Step 3: Candidate selection ───────────────────────────────────────
        candidate_pairs = select_candidate_pairs(doc_id, claims)
        if not candidate_pairs:
            return self._empty_report(doc_id, claim_count=len(claims), pairs_evaluated=0)

        # ── Step 4: Classify + score + evidence + explain ─────────────────────
        contradictions: list[ContradictionPair] = []

        for pair in candidate_pairs:
            # 4a. Classify
            clf_result = classifier_bridge.score_pair(pair.claim_a.text, pair.claim_b.text)
            logger.debug(
                f"[ContradictionPipeline] pair ({pair.idx_a},{pair.idx_b}) "
                f"P(contra)={clf_result.contradiction_prob:.3f} sim={pair.similarity:.3f}"
            )

            # 4b. Score
            confidence = compute_contradiction_confidence(
                clf_result.contradiction_prob, pair.similarity
            )

            if not is_contradiction(confidence):
                continue   # gate: don't run evidence/explain on weak pairs

            # 4c. Extract evidence (only confirmed pairs)
            evidence = extract_evidence(pair.claim_a, pair.claim_b, clf_result.features)

            # 4d. Generate explanation (only confirmed pairs)
            explanation = generate_explanation(
                pair, evidence, confidence, clf_result.used_heuristic
            )

            # Build ContradictionPair schema object
            contradictions.append(ContradictionPair(
                pair_id=str(uuid.uuid4()),
                claim_a=ConflictingFragment(
                    claim_id=pair.claim_a.claim_id,
                    text=pair.claim_a.original,
                    fragment=evidence.fragment_a,
                    source_span=pair.claim_a.source_span,
                ),
                claim_b=ConflictingFragment(
                    claim_id=pair.claim_b.claim_id,
                    text=pair.claim_b.original,
                    fragment=evidence.fragment_b,
                    source_span=pair.claim_b.source_span,
                ),
                similarity_score=round(pair.similarity, 4),
                contradiction_confidence=confidence,
                conflict_type=evidence.conflict_type,
                explanation=explanation,
                features=clf_result.features,
            ))

        elapsed = time.perf_counter() - t0
        logger.info(
            f"[ContradictionPipeline] doc={doc_id}: "
            f"{len(claims)} claims, {len(candidate_pairs)} pairs evaluated, "
            f"{len(contradictions)} contradictions found in {elapsed:.2f}s"
        )

        report = ContradictionReport(
            document_id=doc_id,
            claim_count=len(claims),
            pairs_evaluated=len(candidate_pairs),
            contradiction_count=len(contradictions),
            contradictions=contradictions,
            computed_at=datetime.now(timezone.utc).isoformat(),
        )

        # ── Step 6: Persist ───────────────────────────────────────────────────
        job_manager.store_artifact(doc_id, _CACHE_KEY, report.model_dump())
        return report

    @staticmethod
    def _empty_report(doc_id: str, claim_count: int, pairs_evaluated: int) -> ContradictionReport:
        return ContradictionReport(
            document_id=doc_id,
            claim_count=claim_count,
            pairs_evaluated=pairs_evaluated,
            contradiction_count=0,
            contradictions=[],
            computed_at=datetime.now(timezone.utc).isoformat(),
        )


# Module-level singleton
contradiction_pipeline = ContradictionPipeline()
