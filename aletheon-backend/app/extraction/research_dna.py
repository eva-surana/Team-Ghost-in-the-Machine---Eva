"""Research DNA extraction using extractive generation (no LLM)."""
from __future__ import annotations

import logging
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.embeddings.local_embedder import local_embedder
from app.generation.grounded_generator import extract_field
from app.jobs.manager import job_manager
from app.models.schemas import GroundedClaim, ResearchDNA

logger = logging.getLogger(__name__)

_FALLBACK_CLAIM = lambda doc_id, field: GroundedClaim(
    claim_id=f"{doc_id}_{field}_fallback",
    text=f"[No relevant spans found for '{field}' in this document.]",
    cited_spans=[],
    composition_method="single_span",
    verification_status="unsupported",
    confidence=0.0,
    retrieval_score=0.0,
    entailment_score=0.0,
)


async def extract_research_dna(doc_id: str) -> ResearchDNA:
    """
    Extract the four Research DNA fields using sequential chained extraction.
    Ensures crisp differentiation between problem and gap.
    """
    results = {}

    # 1. Problem
    problem_claim = await extract_field(
        doc_id=doc_id,
        task="problem",
        top_k_retrieve=10,
        composite_threshold=2,
    )
    results["problem"] = problem_claim if problem_claim is not None else _FALLBACK_CLAIM(doc_id, "problem")

    # 2. Gap (sequential context-aware — exclude problem cited spans)
    problem_spans = results["problem"].cited_spans
    gap_claim = await extract_field(
        doc_id=doc_id,
        task="gap",
        top_k_retrieve=10,
        composite_threshold=2,
        exclude_spans=problem_spans,
    )
    results["gap"] = gap_claim if gap_claim is not None else _FALLBACK_CLAIM(doc_id, "gap")

    # 3. Method
    method_claim = await extract_field(
        doc_id=doc_id,
        task="method",
        top_k_retrieve=10,
        composite_threshold=2,
    )
    results["method"] = method_claim if method_claim is not None else _FALLBACK_CLAIM(doc_id, "method")

    # 4. Contribution
    contribution_claim = await extract_field(
        doc_id=doc_id,
        task="contribution",
        top_k_retrieve=10,
        composite_threshold=2,
    )
    results["contribution"] = contribution_claim if contribution_claim is not None else _FALLBACK_CLAIM(doc_id, "contribution")

    # ── Automated Differentiation Check (Problem vs Gap) ───────────────────
    extraction_quality = "high"
    p_text = results["problem"].text
    g_text = results["gap"].text

    if p_text and g_text and not p_text.startswith("[No relevant") and not g_text.startswith("[No relevant"):
        vecs = local_embedder.embed_texts([p_text, g_text])
        sim = float(cosine_similarity(vecs[0:1], vecs[1:2])[0, 0])
        logger.info(f"[Research DNA] Problem vs Gap cosine similarity: {sim:.4f}")

        if sim > settings.PROBLEM_GAP_SIMILARITY_THRESHOLD:
            logger.warning(
                f"[Research DNA] High similarity ({sim:.4f} > {settings.PROBLEM_GAP_SIMILARITY_THRESHOLD}) "
                "between problem and gap. Retrying gap with strengthened query."
            )
            retry_gap = await extract_field(
                doc_id=doc_id,
                task="gap",
                query_override="specific limitation missing capability unsolved drawback bottleneck failure mode",
                top_k_retrieve=10,
                composite_threshold=2,
                exclude_spans=problem_spans,
            )
            if retry_gap:
                results["gap"] = retry_gap
                retry_vecs = local_embedder.embed_texts([p_text, retry_gap.text])
                retry_sim = float(cosine_similarity(retry_vecs[0:1], retry_vecs[1:2])[0, 0])
                logger.info(f"[Research DNA] Retry gap similarity: {retry_sim:.4f}")
                if retry_sim > settings.PROBLEM_GAP_SIMILARITY_THRESHOLD:
                    extraction_quality = "low_differentiation"
            else:
                extraction_quality = "low_differentiation"

    return ResearchDNA(
        document_id=doc_id,
        problem=results["problem"],
        gap=results["gap"],
        method=results["method"],
        contribution=results["contribution"],
        extraction_quality=extraction_quality,
    )
