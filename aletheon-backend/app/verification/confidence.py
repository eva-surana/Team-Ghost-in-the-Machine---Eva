"""Confidence scoring and document fidelity aggregation (updated field names)."""
from __future__ import annotations

from typing import Literal

from app.jobs.manager import job_manager
from app.models.schemas import DocumentFidelityReport

Verdict = Literal["verified", "partially_supported", "unsupported"]

_RETRIEVAL_WEIGHT = 0.4
_ENTAILMENT_WEIGHT = 0.6


def calculate_claim_confidence(
    retrieval_score: float,
    entailment_score: float,
    verdict: Verdict,
) -> float:
    """
    confidence = 0.4 × retrieval_score + 0.6 × entailment_score
    Capped at 0.30 for unsupported; 0.70 for partially_supported.
    """
    raw = _RETRIEVAL_WEIGHT * retrieval_score + _ENTAILMENT_WEIGHT * entailment_score
    if verdict == "unsupported":
        raw = min(raw, 0.30)
    elif verdict == "partially_supported":
        raw = min(raw, 0.70)
    return round(max(0.0, min(1.0, raw)), 4)


async def compute_document_fidelity(doc_id: str) -> DocumentFidelityReport:
    records = job_manager.get_verification_records(doc_id)
    if not records:
        return DocumentFidelityReport(
            document_id=doc_id,
            fidelity_score=1.0,
            claim_count=0,
            verified_count=0,
            partially_supported_count=0,
            unsupported_count=0,
        )
    n_total = len(records)
    n_verified = sum(1 for r in records if r["verdict"] == "verified")
    n_partial = sum(1 for r in records if r["verdict"] == "partially_supported")
    n_unsupported = sum(1 for r in records if r["verdict"] == "unsupported")
    fidelity = (n_verified + 0.5 * n_partial) / n_total
    return DocumentFidelityReport(
        document_id=doc_id,
        fidelity_score=round(fidelity, 4),
        claim_count=n_total,
        verified_count=n_verified,
        partially_supported_count=n_partial,
        unsupported_count=n_unsupported,
    )
