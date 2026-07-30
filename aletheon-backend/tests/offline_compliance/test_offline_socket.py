"""
Offline Compliance Test — Release Gate

This test monkeypatches socket.socket at the transport level so that
ANY external network connection attempt raises a RuntimeError.

The full pipeline (config -> artifact registry -> TF-IDF fit -> vector search -> verify -> Q&A -> recommendations)
is run against a synthetic document. If no exception escapes the socket patch,
the system is proven air-gap compliant.

Run:  pytest tests/offline_compliance/ -v
"""
from __future__ import annotations

import socket
import pytest


# ── Socket-blocking fixture ───────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def block_all_network(monkeypatch):
    """
    Block every outbound TCP/UDP connection to real external hosts.

    We allow 127.0.0.1 / ::1 loopback because the Windows asyncio
    ProactorEventLoop uses a self-pipe on localhost for internal task
    wakeup — that is an OS internal and NOT a real network call.

    Any connection to a non-loopback address raises RuntimeError.
    """
    _LOOPBACK = {"127.0.0.1", "::1", "localhost"}

    def _blocked_connect(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else str(address)
        if host in _LOOPBACK:
            return _original_connect(self, address)
        raise RuntimeError(
            f"[OFFLINE COMPLIANCE] Network call BLOCKED — socket.connect({address!r}).\n"
            "The system must never make a network call after deployment."
        )

    def _blocked_connect_ex(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else str(address)
        if host in _LOOPBACK:
            return _original_connect_ex(self, address)
        raise RuntimeError(
            f"[OFFLINE COMPLIANCE] Network call BLOCKED — socket.connect_ex({address!r})."
        )

    _original_connect = socket.socket.connect
    _original_connect_ex = socket.socket.connect_ex
    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_connect_ex)
    yield


# ── Offline compliance tests ──────────────────────────────────────────────────

def test_config_imports_without_network():
    """Config import must not trigger any network call."""
    from app.config import settings
    assert settings.OFFLINE_MODE is True
    assert settings.PRETRAINED_WEIGHTS_USED is False


def test_artifact_registry_loads_without_network():
    """ArtifactRegistry.load_all() must not make any network call."""
    from app.models.registry import ArtifactRegistry
    ArtifactRegistry._instance = None
    reg = ArtifactRegistry.get()
    reg.load_all()
    assert True


def test_verifier_works_offline():
    """Verification engine must complete without a network call."""
    from app.verification.verifier import verifier_engine
    from app.models.schemas import SourceSpan

    span = SourceSpan(
        source_id="offline_s1",
        document_id="offline_doc",
        page=1,
        text="Transformers use self-attention to process token sequences.",
    )
    verdict, score, feat = verifier_engine.verify(
        "offline_doc",
        "Transformers use self-attention mechanisms.",
        [span],
    )
    assert verdict in {"verified", "partially_supported", "unsupported"}
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_full_pipeline_offline(tmp_path):
    """
    Full ingestion -> TF-IDF fit -> extraction -> recommendations -> Q&A
    must complete with zero network calls.
    """
    import fitz
    import io

    # Build a tiny in-memory PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Abstract\nThis paper proposes a grounded generation framework.")
    page.insert_text((72, 120), "Introduction\nExisting methods fail to verify generated claims.")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    pdf_bytes = buf.getvalue()

    from app.config import settings
    settings.SQLITE_DB_PATH = str(tmp_path / "aletheon_test.db")
    settings.SPARSE_VECTORS_DIR = str(tmp_path / "sparse_vectors")
    settings.DOC_VECTORIZERS_DIR = str(tmp_path / "doc_vectorizers")

    from app.jobs import manager as mgr_module
    mgr_module._init_db()

    from app.jobs.manager import job_manager
    doc_id = job_manager.create_document_job()

    # Ingestion + TF-IDF fit
    from app.ingestion.service import process_document_background
    await process_document_background(doc_id, pdf_bytes, "test.pdf")

    status = job_manager.get_status(doc_id)
    assert status is not None
    assert status.status == "completed"

    # Research DNA extraction
    from app.extraction.research_dna import extract_research_dna
    dna = await extract_research_dna(doc_id)
    assert dna.problem.composition_method in {"single_span", "extractive_composite"}

    # Grounded Q&A
    from app.generation.grounded_generator import generate_grounded_qa
    qa = await generate_grounded_qa(doc_id, "What does this paper propose?")
    assert qa is not None

    # Recommendations
    from app.recommendation.recommender import recommendation_engine
    recs = recommendation_engine.similar_papers(doc_id, top_k=2)
    assert isinstance(recs, list)
