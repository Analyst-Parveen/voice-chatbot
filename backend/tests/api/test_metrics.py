"""Tests for the /metrics endpoint and instrumentation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_metrics_endpoint_exposes_series() -> None:
    # Generate some traffic: a successful turn and a 404 error.
    client.post("/api/chat", json={"message": "metrics please"})
    client.post(
        "/api/feedback",
        json={"message_id": "00000000-0000-0000-0000-000000000000", "rating": "up"},
    )

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "conversation_turns_total" in body
    assert "app_errors_total" in body


def test_conversation_turn_counter_increments() -> None:
    before = _turns_answered(client.get("/metrics").text)
    client.post("/api/chat", json={"message": "count me"})
    after = _turns_answered(client.get("/metrics").text)
    assert after > before


def _turns_answered(metrics_text: str) -> float:
    """Sum conversation_turns_total for outcome=answered across channels."""
    total = 0.0
    for line in metrics_text.splitlines():
        if line.startswith("conversation_turns_total{") and 'outcome="answered"' in line:
            total += float(line.rsplit(" ", 1)[1])
    return total
