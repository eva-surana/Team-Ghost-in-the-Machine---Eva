"""
Integration tests for the REST API — full workflow using TestClient.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.jobs.manager import job_manager
from app.models.schemas import SourceSpan
from app.vectorization.tfidf_service import tfidf_service

client = TestClient(app)


def _setup_completed_doc(text: str = "Aletheon is an evidence-first research platform.") -> str:
    """Create a doc in 'completed' state with one test span."""
    doc_id = job_manager.create_document_job()
    span = SourceSpan(
        source_id=f"{doc_id}_p1_s1_p1",
        document_id=doc_id,
        page=1, section="Abstract", paragraph_offset=1,
        text=text,
    )
    job_manager.store_spans(doc_id, [span])
    tfidf_service.fit_and_store(doc_id, [span])
    job_manager.update_status(doc_id, status="completed", pages_count=1, chunks_count=1)
    return doc_id


def test_upload_rejects_non_pdf():
    r = client.post(
        "/documents",
        files={"file": ("notes.txt", b"just text", "text/plain")},
    )
    assert r.status_code == 400


def test_status_404_for_unknown():
    r = client.get("/documents/non-existent-id/status")
    assert r.status_code == 404


def test_status_returns_completed():
    doc_id = _setup_completed_doc()
    r = client.get(f"/documents/{doc_id}/status")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


def test_evidence_lookup():
    doc_id = _setup_completed_doc()
    source_id = f"{doc_id}_p1_s1_p1"
    r = client.get(f"/documents/{doc_id}/evidence/{source_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["source_id"] == source_id
    assert "Aletheon" in data["text"]


def test_evidence_unknown_source_id():
    doc_id = _setup_completed_doc()
    r = client.get(f"/documents/{doc_id}/evidence/does-not-exist")
    assert r.status_code == 404


def test_research_dna_returns_grounded_claims():
    doc_id = _setup_completed_doc()
    r = client.get(f"/documents/{doc_id}/research-dna")
    assert r.status_code == 200
    data = r.json()
    for field in ("problem", "gap", "method", "contribution"):
        assert field in data
        claim = data[field]
        assert "verification_status" in claim
        assert claim["verification_status"] in {"verified", "partially_supported", "unsupported"}
        assert "composition_method" in claim
        assert claim["composition_method"] in {"single_span", "extractive_composite"}
        assert 0.0 <= claim["confidence"] <= 1.0


def test_dependency_graph_returns_nodes_and_edges():
    doc_id = _setup_completed_doc()
    r = client.get(f"/documents/{doc_id}/dependency-graph")
    assert r.status_code == 200
    data = r.json()
    assert "claim_nodes" in data
    assert "edges" in data


def test_fidelity_report():
    doc_id = _setup_completed_doc()
    r = client.get(f"/documents/{doc_id}/fidelity")
    assert r.status_code == 200
    data = r.json()
    assert "fidelity_score" in data
    assert 0.0 <= data["fidelity_score"] <= 1.0


def test_qa_returns_verified_claims():
    doc_id = _setup_completed_doc()
    r = client.post(f"/documents/{doc_id}/ask", json={"question": "What is Aletheon?"})
    assert r.status_code == 200
    data = r.json()
    assert "answer_spans" in data
    assert len(data["answer_spans"]) > 0
    for claim in data["answer_spans"]:
        assert claim["verification_status"] in {"verified", "partially_supported", "unsupported"}
        assert claim["composition_method"] in {"single_span", "extractive_composite"}


def test_recommendations_similar_papers():
    doc_id = _setup_completed_doc("Transformer models use multi-head self-attention mechanisms.")
    r = client.get(f"/documents/{doc_id}/recommendations/similar-papers?top_k=3")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "corpus_paper_id" in data[0]
    assert "similarity_score" in data[0]


def test_recommendations_missing_citations():
    doc_id = _setup_completed_doc("BM25 is a bag of words information retrieval algorithm.")
    r = client.get(f"/documents/{doc_id}/recommendations/missing-citations?top_k=3")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
