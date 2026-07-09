"""Phase 1 smoke tests: the app boots and the health endpoint responds."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "run_mode" in body
    assert "dependencies" in body


def test_root_banner() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["health"] == "/api/health"
