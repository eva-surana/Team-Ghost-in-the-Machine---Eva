"""
NetworkX + SQLite graph store.

Claims and assumption nodes are stored as NetworkX DiGraph nodes.
Edges carry a 'relation' attribute.

Each document graph is serialised to JSON and stored in a SQLite BLOB
(via doc_artifacts) so it survives process restarts without a dedicated
graph database server.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import networkx as nx

from app.config import settings
from app.jobs.manager import job_manager
from app.models.schemas import ClaimGraphResponse, ClaimNode, AssumptionNode, DependencyEdge, SourceSpan

logger = logging.getLogger(__name__)

_GRAPH_ARTIFACT_KEY = "claim_graph_nx"


def _graph_to_dict(g: nx.DiGraph) -> dict:
    """Serialise a NetworkX graph to a JSON-compatible dict."""
    return nx.node_link_data(g, edges="links")


def _dict_to_graph(d: dict) -> nx.DiGraph:
    return nx.node_link_graph(d, directed=True, edges="links")


class LocalGraphStore:
    """
    In-process NetworkX graph, persisted to SQLite doc_artifacts per document.
    No graph database server required.
    """

    def __init__(self) -> None:
        self._graphs: dict[str, nx.DiGraph] = {}

    def persist_graph(self, graph_data: ClaimGraphResponse) -> None:
        doc_id = graph_data.document_id
        g = nx.DiGraph()

        for node in graph_data.claim_nodes:
            g.add_node(node.claim_id, node_type="claim", text=node.text,
                       source_id=node.source_span.source_id)

        for node in graph_data.assumption_nodes:
            g.add_node(node.assumption_id, node_type="assumption", text=node.text,
                       source_id=node.source_span.source_id)

        for edge in graph_data.edges:
            g.add_edge(edge.from_claim_id, edge.to_claim_id, relation=edge.relation)

        self._graphs[doc_id] = g
        # Persist to SQLite
        try:
            job_manager.store_artifact(doc_id, _GRAPH_ARTIFACT_KEY, _graph_to_dict(g))
        except Exception as exc:
            logger.warning(f"[GraphStore] SQLite persist failed: {exc}")

    def get_graph(self, doc_id: str) -> Optional[ClaimGraphResponse]:
        """Load from in-memory cache or SQLite; reconstruct ClaimGraphResponse."""
        if doc_id not in self._graphs:
            raw = job_manager.get_artifact(doc_id, _GRAPH_ARTIFACT_KEY)
            if raw is None:
                return None
            try:
                g = _dict_to_graph(raw)
                self._graphs[doc_id] = g
            except Exception as exc:
                logger.error(f"[GraphStore] Deserialise failed: {exc}")
                return None

        g = self._graphs[doc_id]
        return self._graph_to_response(doc_id, g)

    @staticmethod
    def _graph_to_response(doc_id: str, g: nx.DiGraph) -> ClaimGraphResponse:
        claim_nodes = []
        assumption_nodes = []
        _DUMMY_SPAN = SourceSpan(
            source_id="unknown", document_id=doc_id,
            page=1, text="[source span not available]"
        )
        for nid, data in g.nodes(data=True):
            span = _DUMMY_SPAN
            if data.get("node_type") == "claim":
                claim_nodes.append(ClaimNode(
                    claim_id=nid,
                    text=data.get("text", ""),
                    source_span=span,
                ))
            else:
                assumption_nodes.append(AssumptionNode(
                    assumption_id=nid,
                    text=data.get("text", ""),
                    source_span=span,
                ))
        edges = [
            DependencyEdge(
                from_claim_id=u,
                to_claim_id=v,
                relation=edata.get("relation", "depends_on"),
            )
            for u, v, edata in g.edges(data=True)
        ]
        return ClaimGraphResponse(
            document_id=doc_id,
            claim_nodes=claim_nodes,
            assumption_nodes=assumption_nodes,
            edges=edges,
        )


# Module-level singleton
graph_store = LocalGraphStore()
