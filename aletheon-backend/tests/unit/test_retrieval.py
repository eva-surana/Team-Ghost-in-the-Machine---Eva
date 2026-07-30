"""Unit tests for sparse retrieval store."""
import pytest
from app.models.schemas import SourceSpan
from app.retrieval.sparse_store import SparseRetriever
from app.vectorization.tfidf_service import tfidf_service
from app.jobs.manager import job_manager


def _make_span(sid: str, text: str, doc_id: str = "retrieval_doc") -> SourceSpan:
    return SourceSpan(
        source_id=sid, document_id=doc_id,
        page=1, section="Test", paragraph_offset=1, text=text,
    )


def test_add_and_search():
    store = SparseRetriever()
    doc_id = "retrieval_test_doc"
    spans = [
        _make_span("s1", "Neural networks use backpropagation for training.", doc_id),
        _make_span("s2", "Vector databases enable fast semantic similarity search.", doc_id),
        _make_span("s3", "Attention mechanisms form the core of transformer architectures.", doc_id),
    ]
    job_manager.store_spans(doc_id, spans)
    tfidf_service.fit_and_store(doc_id, spans)

    results = store.search(doc_id, "neural network training backpropagation", top_k=2)

    assert len(results) > 0
    assert results[0].span.source_id == "s1"
    assert results[0].score > 0.0


def test_empty_document_search():
    store = SparseRetriever()
    results = store.search("nonexistent_doc", "query", top_k=5)
    assert results == []


def test_scores_in_valid_range():
    store = SparseRetriever()
    doc_id = "range_doc"
    spans = [_make_span(f"s{i}", f"Test sentence number {i}.", doc_id) for i in range(5)]
    job_manager.store_spans(doc_id, spans)
    tfidf_service.fit_and_store(doc_id, spans)
    results = store.search(doc_id, "sentence", top_k=5)
    for r in results:
        assert 0.0 <= r.score <= 1.0
