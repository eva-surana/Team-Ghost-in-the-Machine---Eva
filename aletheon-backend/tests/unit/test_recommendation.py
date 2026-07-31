"""Unit tests for CorpusIndex and RecommendationEngine."""

from pathlib import Path
import pytest
from app.models.schemas import SourceSpan
from app.jobs.manager import job_manager
from app.recommendation.corpus_index import CorpusIndex
from app.recommendation.recommender import recommendation_engine

PROJECT_ROOT = Path(__file__).parent.parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"


def test_corpus_index_build_and_find_similar():
    assert CORPUS_DIR.exists()
    index = CorpusIndex.build(CORPUS_DIR)
    assert index.paper_count > 0

    matches = index.find_similar("transformer attention mechanism machine translation", top_k=3)
    assert len(matches) > 0
    assert matches[0].paper_id == "vaswani2017attention"
    assert matches[0].score > 0.0


def test_recommendation_engine_similar_papers():
    doc_id = "rec_test_doc"
    spans = [
        SourceSpan(
            source_id="rec_s1",
            document_id=doc_id,
            page=1,
            section="Abstract",
            text="We introduce BERT, a deep bidirectional transformer language representation model.",
        )
    ]
    from app.models.registry import ArtifactRegistry
    ArtifactRegistry.get().load_all()

    recs = recommendation_engine.similar_papers(doc_id, top_k=3)
    assert len(recs) > 0
    # BERT paper should rank high
    paper_ids = [r.corpus_paper_id for r in recs]
    assert "devlin2019bert" in paper_ids or "vaswani2017attention" in paper_ids
