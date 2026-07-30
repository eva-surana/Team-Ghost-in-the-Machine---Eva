"""Research DNA extraction using extractive generation (no LLM)."""
from __future__ import annotations

import logging

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
    Extract the four Research DNA fields via the extractive generation pipeline.
    Each field retrieves relevant spans, re-ranks by section affinity,
    and composes a grounded claim. No LLM involved.
    """
    results = {}
    for field in ("problem", "gap", "method", "contribution"):
        claim = await extract_field(
            doc_id=doc_id,
            task=field,
            top_k_retrieve=10,
            composite_threshold=2,
        )
        results[field] = claim if claim is not None else _FALLBACK_CLAIM(doc_id, field)

    return ResearchDNA(
        document_id=doc_id,
        problem=results["problem"],
        gap=results["gap"],
        method=results["method"],
        contribution=results["contribution"],
    )
