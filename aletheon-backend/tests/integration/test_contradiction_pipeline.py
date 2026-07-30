"""
Integration tests for the Contradiction Detection API endpoint.

Tests the full round-trip:
  PDF bytes → /documents (upload) → /documents/{id}/contradictions

Seeded contradictions are embedded in a synthetic PDF with two
factually conflicting claims about accuracy figures and one negation
conflict — the pipeline should surface at least one pair.
"""
from __future__ import annotations

import io
import time

import fitz                   # PyMuPDF — already in requirements
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_contradiction_pdf() -> bytes:
    """
    Create a synthetic PDF with deliberately seeded contradictions:
      - Page 1: "achieves 95% accuracy"
      - Page 3: "achieves only 70% accuracy"    ← numeric conflict with page 1
      - Page 2: "training converges reliably"
      - Page 4: "training does not converge"    ← negation conflict with page 2
      - Page 5: neutral method description (filler)
    """
    doc = fitz.open()

    def add_page(text: str) -> None:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)

    add_page(
        "Results\n\n"
        "The proposed transformer model achieves 95% accuracy on the standard "
        "NLP benchmark evaluation suite. This result surpasses all previously "
        "published baselines by a significant margin."
    )
    add_page(
        "Training Procedure\n\n"
        "We observe that training converges reliably within 50 epochs across "
        "all dataset splits. The learning rate schedule is critical to stable "
        "convergence behavior in deep neural networks."
    )
    add_page(
        "Ablation Study\n\n"
        "Under equivalent experimental conditions with identical hyperparameters, "
        "the proposed transformer model achieves only 70% accuracy on the NLP "
        "benchmark, suggesting sensitivity to data distribution shifts."
    )
    add_page(
        "Limitations\n\n"
        "We note that training does not converge reliably when the batch size "
        "is reduced below 32. This instability is observed across all dataset "
        "configurations tested in our experimental setup."
    )
    add_page(
        "Conclusion\n\n"
        "We presented a novel attention-based architecture that demonstrates "
        "competitive performance on natural language processing tasks. Future "
        "work will explore applications to cross-lingual transfer learning."
    )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def contradiction_doc_id():
    """Upload the synthetic contradiction PDF and return its doc_id."""
    pdf_bytes = _make_contradiction_pdf()
    r = client.post(
        "/documents",
        files={"file": ("contradiction_test.pdf", pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 202, f"Upload failed: {r.json()}"
    doc_id = r.json()["document_id"]

    # Wait for ingestion to complete (up to 15s)
    deadline = time.time() + 15
    while time.time() < deadline:
        sr = client.get(f"/documents/{doc_id}/status")
        if sr.json()["status"] == "completed":
            break
        time.sleep(0.5)
    else:
        pytest.fail(f"Document {doc_id} did not complete ingestion in time")

    return doc_id


class TestContradictionAPI:

    def test_endpoint_returns_200(self, contradiction_doc_id):
        r = client.get(f"/documents/{contradiction_doc_id}/contradictions")
        assert r.status_code == 200, f"Unexpected response: {r.json()}"

    def test_response_schema_valid(self, contradiction_doc_id):
        r = client.get(f"/documents/{contradiction_doc_id}/contradictions")
        data = r.json()
        assert "document_id" in data
        assert "claim_count" in data
        assert "pairs_evaluated" in data
        assert "contradiction_count" in data
        assert "contradictions" in data
        assert "computed_at" in data
        assert data["document_id"] == contradiction_doc_id

    def test_claim_count_positive(self, contradiction_doc_id):
        r = client.get(f"/documents/{contradiction_doc_id}/contradictions")
        data = r.json()
        assert data["claim_count"] >= 1

    def test_contradiction_pairs_have_valid_source_spans(self, contradiction_doc_id):
        r = client.get(f"/documents/{contradiction_doc_id}/contradictions")
        data = r.json()
        for pair in data["contradictions"]:
            assert pair["claim_a"]["source_span"]["page"] >= 1
            assert pair["claim_b"]["source_span"]["page"] >= 1
            assert pair["claim_a"]["source_span"]["document_id"] == contradiction_doc_id
            assert pair["claim_b"]["source_span"]["document_id"] == contradiction_doc_id

    def test_contradiction_confidence_in_unit_interval(self, contradiction_doc_id):
        r = client.get(f"/documents/{contradiction_doc_id}/contradictions")
        data = r.json()
        for pair in data["contradictions"]:
            assert 0.0 <= pair["contradiction_confidence"] <= 1.0
            assert 0.0 <= pair["similarity_score"] <= 1.0

    def test_explanation_is_non_empty_string(self, contradiction_doc_id):
        r = client.get(f"/documents/{contradiction_doc_id}/contradictions")
        data = r.json()
        for pair in data["contradictions"]:
            assert isinstance(pair["explanation"], str)
            assert len(pair["explanation"]) > 10

    def test_conflict_type_is_valid_enum(self, contradiction_doc_id):
        r = client.get(f"/documents/{contradiction_doc_id}/contradictions")
        data = r.json()
        valid_types = {"numeric_conflict", "negation_conflict", "semantic_conflict"}
        for pair in data["contradictions"]:
            assert pair["conflict_type"] in valid_types

    def test_result_is_cached_on_second_call(self):
        """
        Use a fresh isolated document to prove caching invariant
        independent of the module-scoped fixture's call history.
        """
        import io, time, fitz
        doc = fitz.open()
        for i in range(4):
            p = doc.new_page()
            p.insert_text((72, 72),
                f"Page {i+1}: The proposed model achieves {90-i*5}% accuracy "
                f"on the benchmark evaluation suite used in our experiments.",
                fontsize=11)
        buf = io.BytesIO()
        doc.save(buf)

        r = client.post("/documents",
                        files={"file": ("cache_test.pdf", buf.getvalue(), "application/pdf")})
        assert r.status_code == 202
        doc_id = r.json()["document_id"]

        deadline = time.time() + 15
        while time.time() < deadline:
            if client.get(f"/documents/{doc_id}/status").json()["status"] == "completed":
                break
            time.sleep(0.3)

        # First call — computes and caches
        r1 = client.get(f"/documents/{doc_id}/contradictions")
        assert r1.status_code == 200
        ts1 = r1.json()["computed_at"]

        # Second call — must serve from cache (identical computed_at)
        r2 = client.get(f"/documents/{doc_id}/contradictions")
        assert r2.status_code == 200
        ts2 = r2.json()["computed_at"]

        assert ts1 == ts2, f"Cache miss: {ts1!r} != {ts2!r}"


    def test_404_for_unknown_document(self):
        r = client.get("/documents/does-not-exist-xyz/contradictions")
        assert r.status_code == 404

    def test_202_for_processing_document(self):
        from app.jobs.manager import job_manager
        doc_id = job_manager.create_document_job()
        # Leave in "processing" state
        r = client.get(f"/documents/{doc_id}/contradictions")
        assert r.status_code == 202
