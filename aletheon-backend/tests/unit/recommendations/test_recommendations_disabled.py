"""
Test: Disabled-by-Default Isolation (Required per spec §6)

This test proves that the feature flag is a REAL boundary, not just documentation:
  - With ENABLE_ONLINE_RECOMMENDATIONS=false (the default)
  - AND with network access blocked via socket-patching
  - Calling GET /documents/{id}/recommendations returns cleanly
    with available:false, reason:"feature_disabled"
  - WITHOUT ever touching connectivity.py or any HTTP client

Two sub-tests:
  1. Response shape is correct when disabled
  2. No network calls are made even when the endpoint is called
"""
import socket
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.jobs.manager import job_manager
from app.models.schemas import SourceSpan
from app.vectorization.tfidf_service import tfidf_service


def _setup_doc() -> str:
    doc_id = job_manager.create_document_job()
    span = SourceSpan(
        source_id=f"{doc_id}_s1",
        document_id=doc_id,
        page=1,
        section="Abstract",
        text="Attention-based neural networks for natural language processing.",
    )
    job_manager.store_spans(doc_id, [span])
    tfidf_service.fit_and_store(doc_id, [span])
    job_manager.update_status(doc_id, status="completed", pages_count=1, chunks_count=1)
    return doc_id


# ── Test 1: Correct response shape when disabled ─────────────────────────────

def test_recommendations_disabled_returns_feature_disabled(monkeypatch):
    """
    When ENABLE_ONLINE_RECOMMENDATIONS=false, the endpoint must return
    available:false with reason:feature_disabled — never touching the network.
    """
    monkeypatch.setattr(settings, "ENABLE_ONLINE_RECOMMENDATIONS", False)
    doc_id = _setup_doc()

    client = TestClient(app)
    r = client.get(f"/documents/{doc_id}/recommendations")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is False
    assert data["reason"] == "feature_disabled"
    assert data["recommendations"] == []
    assert data["source_mode"] == "unavailable"


# ── Test 2: No network calls when disabled ────────────────────────────────────

def test_recommendations_disabled_makes_zero_network_calls(monkeypatch):
    """
    The structural boundary test: network is patched to raise RuntimeError
    on any non-loopback socket connection. With the feature disabled, calling
    the recommendations endpoint must complete without any network access.
    """
    monkeypatch.setattr(settings, "ENABLE_ONLINE_RECOMMENDATIONS", False)

    _LOOPBACK = {"127.0.0.1", "::1", "localhost"}
    network_calls = []

    def _blocked_connect(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else str(address)
        if host not in _LOOPBACK:
            network_calls.append(address)
            raise RuntimeError(f"NETWORK CALL BLOCKED: {address}")
        return _original_connect(self, address)

    _original_connect = socket.socket.connect
    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)

    doc_id = _setup_doc()
    client = TestClient(app)
    r = client.get(f"/documents/{doc_id}/recommendations")

    assert r.status_code == 200
    assert r.json()["available"] is False
    # The critical assertion: no network call was attempted
    assert network_calls == [], (
        f"ISOLATION BREACH: {len(network_calls)} network call(s) made despite feature being disabled: {network_calls}"
    )


# ── Test 3: Refresh endpoint also respects the flag ──────────────────────────

def test_refresh_endpoint_disabled_returns_feature_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_ONLINE_RECOMMENDATIONS", False)
    doc_id = _setup_doc()
    client = TestClient(app)
    r = client.post(f"/documents/{doc_id}/recommendations/refresh")
    assert r.status_code == 200
    assert r.json()["available"] is False
    assert r.json()["reason"] == "feature_disabled"


# ── Test 4: system/health reports recommendations_enabled correctly ───────────

def test_system_health_reports_recommendations_enabled_false(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_ONLINE_RECOMMENDATIONS", False)
    client = TestClient(app)
    r = client.get("/system/health")
    assert r.status_code == 200
    data = r.json()
    assert "recommendations_enabled" in data
    assert data["recommendations_enabled"] is False
