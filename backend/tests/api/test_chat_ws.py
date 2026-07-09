"""WebSocket streaming tests for /ws/chat and /ws/voice."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _drain_turn(ws) -> tuple[str, list[str], dict]:
    """Collect one streamed turn: (session_id, tokens, done_event)."""
    session_id = ""
    tokens: list[str] = []
    while True:
        event = ws.receive_json()
        if event["type"] == "session":
            session_id = event["session_id"]
        elif event["type"] == "token":
            tokens.append(event["token"])
        elif event["type"] == "done":
            return session_id, tokens, event
        elif event["type"] == "error":
            raise AssertionError(f"server error event: {event}")


def test_chat_ws_streams_tokens_and_persists() -> None:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "message", "message": "Stream this"})
        session_id, tokens, done = _drain_turn(ws)

    assert session_id
    assert tokens, "expected at least one streamed token"
    answer = "".join(tokens)
    assert "Stream this" in answer
    assert done["message_id"]
    assert done["latency_ms"] >= 0

    # The streamed answer was persisted verbatim (identical text rule).
    hist = client.get(f"/api/history/{session_id}").json()
    assistant = [m for m in hist["messages"] if m["role"] == "assistant"][0]
    assert assistant["content"] == answer


def test_chat_ws_empty_message_error() -> None:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "message", "message": "   "})
        event = ws.receive_json()
        assert event["type"] == "error"
        assert event["code"] == "empty_message"


def test_voice_ws_text_path() -> None:
    with client.websocket_connect("/ws/voice") as ws:
        info = ws.receive_json()
        assert info["type"] == "info"
        ws.send_json({"type": "message", "message": "over voice socket"})
        # First event of the turn is the session announcement.
        event = ws.receive_json()
        assert event["type"] == "session"
