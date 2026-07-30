"""Unit tests for TF-IDF vectorization service and sparse retriever."""

import pytest
from app.models.schemas import SourceSpan
from app.retrieval.sparse_store import SparseRetriever
from app.vectorization.tfidf_service import TFIDFService


def _make_span(sid: str, text: str, doc_id: str = "tfidf_test_doc") -> SourceSpan:
    return SourceSpan(
        source_id=sid,
        document_id=doc_id,
        page=1,
        section="Test",
        paragraph_offset=1,
        text=text,
    )


def test_tfidf_fit_and_query():
    service = TFIDFService()
    doc_id = "tfidf_test_doc"
    spans = [
        _make_span("s1", "Neural networks use backpropagation for training.", doc_id),
        _make_span("s2", "Vector databases enable fast semantic similarity search.", doc_id),
        _make_span("s3", "Attention mechanisms form the core of transformer architectures.", doc_id),
    ]

    service.fit_and_store(doc_id, spans)
    assert service.has_index(doc_id)

    q_matrix = service.vectorize_query(doc_id, "neural network training")
    assert q_matrix is not None
    assert q_matrix.shape[0] == 1


def test_sparse_retriever_search():
    service = TFIDFService()
    retriever = SparseRetriever()
    doc_id = "retrieval_sparse_doc"
    spans = [
        _make_span("s1", "Neural networks use backpropagation for training.", doc_id),
        _make_span("s2", "Vector databases enable fast semantic similarity search.", doc_id),
        _make_span("s3", "Attention mechanisms form the core of transformer architectures.", doc_id),
    ]

    from app.jobs.manager import job_manager
    job_manager.store_spans(doc_id, spans)
    service.fit_and_store(doc_id, spans)

    results = retriever.search(doc_id, "neural network training backpropagation", top_k=2)
    assert len(results) > 0
    assert results[0].span.source_id == "s1"
    assert results[0].score > 0.0
