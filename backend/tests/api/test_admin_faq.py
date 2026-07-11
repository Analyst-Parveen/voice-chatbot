"""Admin FAQ endpoint smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_intents_empty_ok() -> None:
    resp = client.get("/api/admin/faq/intents")
    assert resp.status_code == 200
    body = resp.json()
    assert "intents" in body
    assert "total" in body


def test_reindex_empty_ok() -> None:
    resp = client.post("/api/admin/faq/reindex")
    assert resp.status_code == 200
    assert "indexed" in resp.json()
