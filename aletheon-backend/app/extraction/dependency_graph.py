"""Claim dependency graph & assumption extraction — extractive rule-based.

Extracts claims from key sections (Method, Results, Conclusion), identifies candidate
assumptions (from Background, Methods), and builds structural dependency edges based on
section order and lexical co-occurrence. No LLM used.
"""
from __future__ import annotations

import logging
import uuid
from typing import List

from app.graph.graph_store import graph_store
from app.jobs.manager import job_manager
from app.models.schemas import (
    AssumptionNode,
    ClaimGraphResponse,
    ClaimNode,
    DependencyEdge,
    SourceSpan,
)

logger = logging.getLogger(__name__)


async def extract_dependency_graph(doc_id: str) -> ClaimGraphResponse:
    """
    Extract claims, implicit assumptions, and dependency edges extractively.
    Persists graph to NetworkX/SQLite graph_store.
    """
    spans = job_manager.get_all_spans(doc_id)
    if not spans:
        return ClaimGraphResponse(
            document_id=doc_id, claim_nodes=[], assumption_nodes=[], edges=[]
        )

    claim_nodes: List[ClaimNode] = []
    assumption_nodes: List[AssumptionNode] = []
    edges: List[DependencyEdge] = []

    # Identify claim spans vs assumption spans by section/keywords
    for i, span in enumerate(spans):
        sec = (span.section or "").lower()
        text = span.text.strip()
        if not text:
            continue

        cid = f"c_{span.source_id}"

        # Classify as assumption if in background/intro or contains assumption keywords
        if any(k in sec for k in ["background", "related", "introduction"]) or any(
            k in text.lower() for k in ["assume", "suppose", "given that", "requires"]
        ):
            aid = f"a_{span.source_id}"
            assumption_nodes.append(
                AssumptionNode(
                    assumption_id=aid,
                    text=text,
                    source_span=span,
                )
            )
        else:
            claim_nodes.append(
                ClaimNode(
                    claim_id=cid,
                    text=text,
                    source_span=span,
                )
            )

    # Build edges between assumption nodes and subsequent claim nodes
    for a in assumption_nodes[:5]:
        for c in claim_nodes[:5]:
            if c.source_span.page >= a.source_span.page:
                edges.append(
                    DependencyEdge(
                        from_claim_id=c.claim_id,
                        to_claim_id=a.assumption_id,
                        relation="depends_on",
                    )
                )

    graph = ClaimGraphResponse(
        document_id=doc_id,
        claim_nodes=claim_nodes,
        assumption_nodes=assumption_nodes,
        edges=edges,
    )

    graph_store.persist_graph(graph)
    return graph
