"""
Grounded extractive generation orchestrator.

Replaces the LLM-based grounded_generator from the previous design.
No language model. No hub calls. Every returned claim is a verbatim
excerpt from the source document, with citation built-in by construction.

Pipeline per field:
  1. Retrieve top-k spans via sparse TF-IDF cosine similarity
  2. Re-rank by section affinity (task-specific weights)
  3. Compose claim via single_span or extractive_composite
  4. Verify with self-trained entailment classifier
  5. Compute confidence from retrieval_score + entailment_score
  6. Return GroundedClaim

Q&A pipeline:
  Same as above but using the user's question as the retrieval query,
  with section weights set to "qa" (neutral / query-driven only).
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator, List, Optional

from app.config import settings
from app.generation.extractor import compose_claim, extract_precise_answer_sentence
from app.generation.span_selector import rank_spans
from app.jobs.manager import job_manager
from app.models.schemas import GroundedClaim, QAResponse, SourceSpan
from app.retrieval.sparse_store import SearchResult, sparse_retriever
from app.verification.verifier import verifier_engine
from app.verification.confidence import calculate_claim_confidence

logger = logging.getLogger(__name__)

# ── Task → retrieval query templates ─────────────────────────────────────────
_TASK_QUERIES = {
    "problem": "broad problem motivation challenge domain need real-world importance application",
    "gap": "specific limitation prior work missing unsolved bottleneck drawback weakness existing methods lack",
    "method": "proposed method approach algorithm model architecture design technique mechanism",
    "contribution": "contribution novelty result empirical finding performance key improvement state-of-the-art",
}


async def extract_field(
    doc_id: str,
    task: str,
    query_override: Optional[str] = None,
    top_k_retrieve: int = 10,
    composite_threshold: int = 2,
    exclude_spans: Optional[List[SourceSpan]] = None,
) -> Optional[GroundedClaim]:
    """
    Extract a single grounded claim for the given task field.
    Returns None if no relevant spans are found.
    """
    query = query_override or _TASK_QUERIES.get(task, task)

    # Step 1 & 2: Retrieve + section-weighted re-rank
    results = sparse_retriever.search(doc_id=doc_id, query=query, top_k=top_k_retrieve * 2)
    if exclude_spans:
        ex_ids = {s.source_id for s in exclude_spans}
        results = [r for r in results if r.span.source_id not in ex_ids]

    if not results:
        all_spans = job_manager.get_all_spans(doc_id)
        if exclude_spans:
            ex_ids = {s.source_id for s in exclude_spans}
            all_spans = [s for s in all_spans if s.source_id not in ex_ids]
        if not all_spans:
            return None
        results = [SearchResult(span=s, score=0.1) for s in all_spans[:top_k_retrieve]]

    ranked = rank_spans(results, task=task, top_k=top_k_retrieve)

    # Step 3: Compose claim
    claim = compose_claim(ranked, min_score=0.0, composite_threshold=composite_threshold)
    if claim is None:
        return None

    # Step 4: Verify
    verdict, ent_score, features = verifier_engine.verify(
        doc_id=doc_id,
        claim_text=claim.text,
        cited_spans=claim.cited_spans,
    )

    # Step 5: Confidence
    confidence = calculate_claim_confidence(claim.retrieval_score, ent_score, verdict)

    claim.verification_status = verdict
    claim.entailment_score = round(ent_score, 4)
    claim.confidence = confidence
    claim.verifier_features = features

    return claim


async def generate_grounded_qa(doc_id: str, question: str) -> QAResponse:
    """
    Extractive Q&A: retrieve top-k spans most relevant to the question,
    return verified/partially_supported spans as GroundedClaims.
    Stage-by-stage logging instrumented per diagnostic spec.
    """
    results = sparse_retriever.search(doc_id=doc_id, query=question, top_k=settings.RETRIEVAL_TOP_K)
    scores = [round(r.score, 4) for r in results]
    logger.info(f"[QA Diagnostic] Stage 1 (Retrieval): retrieved {len(results)} chunks for doc {doc_id}. Similarity scores: {scores}")

    if not results:
        all_spans = job_manager.get_all_spans(doc_id)
        results = [SearchResult(span=s, score=0.1) for s in all_spans[:settings.RETRIEVAL_TOP_K]]
        logger.info(f"[QA Diagnostic] Stage 1 Fallback: retrieved {len(results)} fallback spans from doc {doc_id}")

    ranked = rank_spans(results, task="qa", top_k=settings.RETRIEVAL_TOP_K)
    logger.info(f"[QA Diagnostic] Stage 2 (Ranker): {len(ranked)} candidate spans entering verifier")

    claims: List[GroundedClaim] = []

    for r, boosted_score in ranked:
        span = r.span
        precise_text = extract_precise_answer_sentence(question, span.text)
        verdict, ent_score, features = verifier_engine.verify(
            doc_id=doc_id,
            claim_text=precise_text,
            cited_spans=[span],
        )
        confidence = calculate_claim_confidence(r.score, ent_score, verdict)
        logger.info(f"[QA Diagnostic] Stage 3 (Verifier): span='{precise_text[:40]}...' verdict={verdict} ent_score={ent_score:.4f} conf={confidence:.4f}")

        if verdict in ("verified", "partially_supported"):
            claims.append(GroundedClaim(
                claim_id=str(uuid.uuid4()),
                text=precise_text,
                cited_spans=[span],
                composition_method="single_span",
                verification_status=verdict,
                confidence=confidence,
                retrieval_score=round(r.score, 4),
                entailment_score=round(ent_score, 4),
                verifier_features=features,
            ))

    logger.info(f"[QA Diagnostic] Stage 4 (Summary): {len(claims)} / {len(ranked)} claims survived verification")

    reason = None
    if not claims:
        reason = "no_verified_claims_found"

    return QAResponse(
        document_id=doc_id,
        question=question,
        answer_spans=claims,
        reason=reason,
    )


async def generate_grounded_qa_stream(doc_id: str, question: str) -> AsyncGenerator[str, None]:
    """
    Generator yielding SSE formatted event strings for real-time Q&A streaming.
    Yields:
      event: status\ndata: {"stage": "searching"}\n\n
      event: claim\ndata: {...}\n\n
      event: end\ndata: {"reason": null}\n\n
    """
    results = sparse_retriever.search(doc_id=doc_id, query=question, top_k=settings.RETRIEVAL_TOP_K)
    if not results:
        all_spans = job_manager.get_all_spans(doc_id)
        results = [SearchResult(span=s, score=0.1) for s in all_spans[:settings.RETRIEVAL_TOP_K]]

    ranked = rank_spans(results, task="qa", top_k=settings.RETRIEVAL_TOP_K)

    yield f"event: status\ndata: {json.dumps({'stage': 'verifying', 'total': len(ranked)})}\n\n"

    found_count = 0
    for r, boosted_score in ranked:
        span = r.span
        precise_text = extract_precise_answer_sentence(question, span.text)
        verdict, ent_score, features = verifier_engine.verify(
            doc_id=doc_id,
            claim_text=precise_text,
            cited_spans=[span],
        )
        confidence = calculate_claim_confidence(r.score, ent_score, verdict)

        if verdict in ("verified", "partially_supported"):
            found_count += 1
            claim = GroundedClaim(
                claim_id=str(uuid.uuid4()),
                text=precise_text,
                cited_spans=[span],
                composition_method="single_span",
                verification_status=verdict,
                confidence=confidence,
                retrieval_score=round(r.score, 4),
                entailment_score=round(ent_score, 4),
                verifier_features=features,
            )
            yield f"event: claim\ndata: {claim.model_dump_json()}\n\n"

    reason = "no_verified_claims_found" if found_count == 0 else None
    yield f"event: end\ndata: {json.dumps({'reason': reason})}\n\n"

