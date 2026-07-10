"""Preferences API — widget theme/language/voice persistence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_put_preferences_creates_row() -> None:
    resp = client.put(
        "/api/preferences",
        json={
            "user_ref": "widget-test-1",
            "theme": "dark",
            "language": "Hindi",
            "voice_enabled": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_ref"] == "widget-test-1"
    assert body["theme"] == "dark"
    assert body["language"] == "hi"
    assert body["voice_enabled"] is True

    # Idempotent update merges fields.
    resp2 = client.put(
        "/api/preferences",
        json={"user_ref": "widget-test-1", "theme": "light"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["theme"] == "light"
    assert resp2.json()["language"] == "hi"
