"""End-to-end Phase 4 tests: text chat, history, feedback, session lifecycle."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_chat_creates_session_and_persists_history() -> None:
    # First message auto-creates a session.
    resp = client.post("/api/chat", json={"message": "Hello there"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"]
    assert body["message_id"]
    assert "Hello there" in body["answer"]  # stub echo
    assert body["latency_ms"] >= 0
    assert body["sources"] == []  # no RAG in stub mode

    session_id = body["session_id"]

    # Follow-up in the same session.
    resp2 = client.post("/api/chat", json={"session_id": session_id, "message": "Second"})
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == session_id

    # History has 4 messages: 2 user + 2 assistant, chronological.
    hist = client.get(f"/api/history/{session_id}")
    assert hist.status_code == 200
    hbody = hist.json()
    assert hbody["total"] == 4
    roles = [m["role"] for m in hbody["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert hbody["messages"][0]["content"] == "Hello there"


def test_feedback_on_message() -> None:
    chat = client.post("/api/chat", json={"message": "Rate me"}).json()
    resp = client.post(
        "/api/feedback",
        json={"message_id": chat["message_id"], "rating": "up", "comment": "nice"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "recorded"


def test_feedback_unknown_message_404() -> None:
    resp = client.post(
        "/api/feedback",
        json={"message_id": "00000000-0000-0000-0000-000000000000", "rating": "down"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_session_create_and_clear() -> None:
    created = client.post("/api/session", json={"channel": "text"})
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    # Add a message, then clear the whole conversation.
    client.post("/api/chat", json={"session_id": session_id, "message": "hi"})
    deleted = client.delete(f"/api/session/{session_id}")
    assert deleted.status_code == 204

    # Session is gone → history is empty.
    hist = client.get(f"/api/history/{session_id}")
    assert hist.json()["total"] == 0


def test_clear_unknown_session_404() -> None:
    resp = client.delete("/api/session/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_suggestions() -> None:
    resp = client.get("/api/suggestions")
    assert resp.status_code == 200
    assert len(resp.json()["suggestions"]) > 0


def test_suggestions_hindi() -> None:
    resp = client.get("/api/suggestions", params={"language": "Hindi"})
    assert resp.status_code == 200
    questions = resp.json()["suggestions"]
    assert len(questions) == 4
    assert any("\u0900" <= ch <= "\u097f" for q in questions for ch in q)


def test_starter_faq_skips_llm() -> None:
    resp = client.post(
        "/api/chat",
        json={"message": "What is your return policy?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "30 days" in body["answer"]
    assert "stub" not in body["answer"].lower()


def test_starter_faq_hindi() -> None:
    resp = client.post(
        "/api/chat",
        json={
            "message": "आपकी रिटर्न पॉलिसी क्या है?",
            "language": "Hindi",
        },
    )
    assert resp.status_code == 200
    assert "30 दिन" in resp.json()["answer"]


def test_empty_message_rejected() -> None:
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422  # pydantic min_length
