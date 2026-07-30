"""Unit tests for health endpoints."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_system_health_offline_and_no_pretrained():
    r = client.get("/system/health")
    assert r.status_code == 200
    data = r.json()
    assert data["offline_mode"] is True
    assert data["pretrained_weights_used"] is False
    assert "entailment_classifier_loaded" in data
    assert "corpus_index_loaded" in data
    assert "corpus_paper_count" in data
