"""
Recommendation engine — similar-papers + missing-citations.

Both outputs are content-based, using the same TF-IDF machinery.
No pretrained knowledge about which papers are "related" —
similarity is entirely driven by lexical overlap in the corpus text.

Similar papers:
  Query = ingested document's full text (or abstract if available).
  Ranking = cosine similarity between query vector and corpus paper vectors.

Missing citations:
  For each claim in the dependency graph that has zero or weak internal
  citation support, use the claim text as the query against the corpus.
  Surface top-k corpus papers as candidate references for human review.
  The rationale_span from the corpus abstract is returned so the user
  can judge whether the match is a genuine citation gap or coincidental
  lexical overlap.  Never auto-inserts a citation.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.config import settings
from app.jobs.manager import job_manager
from app.models.registry import ArtifactRegistry
from app.models.schemas import (
    MissingCitationSuggestion,
    RecommendedPaper,
    SourceSpan,
)
from app.recommendation.corpus_index import CorpusIndex

logger = logging.getLogger(__name__)


class RecommendationEngine:

    def similar_papers(
        self,
        doc_id: str,
        top_k: Optional[int] = None,
    ) -> List[RecommendedPaper]:
        """
        Find corpus papers similar to the ingested document.

        Uses the full text of all ingested spans as the query to the corpus index.
        Returns RecommendedPaper list sorted by similarity_score descending.
        """
        top_k = top_k or settings.RECOMMENDATION_TOP_K
        index = self._get_index()
        if index is None:
            logger.warning("[Recommender] Corpus index not loaded — returning empty list")
            return []

        # Build query from document spans
        spans = job_manager.get_all_spans(doc_id)
        if not spans:
            logger.warning(f"[Recommender] No spans for doc {doc_id}")
            return []

        query_text = " ".join(s.text for s in spans)
        matches = index.find_similar(query_text, top_k=top_k)

        results = []
        for m in matches:
            # Identify which sections of the document drove the match
            matched_on = _identify_matched_sections(spans, m.rationale_span)
            results.append(RecommendedPaper(
                corpus_paper_id=m.paper_id,
                title=m.title,
                similarity_score=m.score,
                matched_on=matched_on,
            ))
        return results

    def missing_citations(
        self,
        doc_id: str,
        top_k: Optional[int] = None,
    ) -> List[MissingCitationSuggestion]:
        """
        Find claims in the dependency graph with weak/no internal citation support,
        and suggest corpus papers that might fill the citation gap.

        Returns MissingCitationSuggestion list for human review.
        """
        top_k = top_k or settings.MISSING_CITATION_TOP_K
        index = self._get_index()
        if index is None:
            return []

        # Get dependency graph artifact
        graph_data = job_manager.get_dependency_graph(doc_id)
        if not graph_data:
            logger.info(f"[Recommender] No dependency graph for doc {doc_id} — using all spans as claims")
            return self._spans_as_claims(doc_id, index, top_k)

        suggestions: List[MissingCitationSuggestion] = []
        claim_nodes = graph_data.get("claim_nodes", [])

        for node in claim_nodes:
            claim_text = node.get("text", "")
            claim_id = node.get("claim_id", "")
            if not claim_text:
                continue

            matches = index.find_similar(claim_text, top_k=2)
            for m in matches:
                if m.score < 0.05:  # too weak to be a meaningful suggestion
                    continue
                suggestions.append(MissingCitationSuggestion(
                    claim_id=claim_id,
                    claim_text=claim_text,
                    candidate_paper_id=m.paper_id,
                    candidate_title=m.title,
                    similarity_score=m.score,
                    rationale_span=m.rationale_span,
                ))

        # Sort by similarity and deduplicate by paper
        suggestions.sort(key=lambda s: s.similarity_score, reverse=True)
        return suggestions[:top_k]

    def _spans_as_claims(
        self, doc_id: str, index: CorpusIndex, top_k: int
    ) -> List[MissingCitationSuggestion]:
        """Fallback: treat each document span as a claim when no graph exists."""
        spans = job_manager.get_all_spans(doc_id)
        suggestions = []
        for span in spans[:15]:   # limit to avoid excessive computation
            matches = index.find_similar(span.text, top_k=1)
            for m in matches:
                if m.score < 0.05:
                    continue
                suggestions.append(MissingCitationSuggestion(
                    claim_id=span.source_id,
                    claim_text=span.text[:150],
                    candidate_paper_id=m.paper_id,
                    candidate_title=m.title,
                    similarity_score=m.score,
                    rationale_span=m.rationale_span,
                ))
        suggestions.sort(key=lambda s: s.similarity_score, reverse=True)
        return suggestions[:top_k]

    @staticmethod
    def _get_index() -> Optional[CorpusIndex]:
        reg = ArtifactRegistry.get()
        if reg.corpus_index_loaded:
            return reg.corpus_index
        return None


def _identify_matched_sections(spans: List[SourceSpan], rationale: str) -> List[str]:
    """Return the document section names whose text best overlaps the corpus rationale."""
    rationale_words = set(rationale.lower().split())
    section_scores: dict[str, float] = {}

    for span in spans:
        if not span.section:
            continue
        span_words = set(span.text.lower().split())
        overlap = len(span_words & rationale_words) / max(len(span_words | rationale_words), 1)
        sec = span.section
        if sec not in section_scores or overlap > section_scores[sec]:
            section_scores[sec] = overlap

    # Return top-3 sections by overlap
    sorted_secs = sorted(section_scores.items(), key=lambda x: x[1], reverse=True)
    return [s for s, _ in sorted_secs[:3] if section_scores[s] > 0.01]


# Module-level singleton
recommendation_engine = RecommendationEngine()
