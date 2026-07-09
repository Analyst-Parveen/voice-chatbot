"""Voice WebSocket pipeline tests (stub STT/TTS).

Verifies the full turn (transcript → streamed tokens → audio → done), the
identical-text-and-voice rule (persisted answer == streamed tokens), and that
interrupt/barge-in keeps the socket healthy.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _drain(ws) -> list[dict]:
    events = []
    while True:
        e = ws.receive_json()
        events.append(e)
        if e["type"] in ("done", "error"):
            return events


def test_voice_turn_audio_to_speech() -> None:
    with client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["type"] == "info"  # "voice ready"
        ws.send_json({"type": "audio_start", "session_id": None})
        ws.send_bytes(b"\x00\x01\x02\x03")  # dummy audio (stub ignores content)
        ws.send_json({"type": "audio_end"})
        events = _drain(ws)

    types = [e["type"] for e in events]
    assert "transcript" in types
    assert "session" in types
    assert "say" in types            # sentence text + its audio, together
    assert types[-1] == "done"

    transcript = next(e["text"] for e in events if e["type"] == "transcript")
    says = [e for e in events if e["type"] == "say"]
    assert says and all(s["text"] for s in says)
    assert any(s["audio"] for s in says)  # TTS produced audio
    answer = "".join(s["text"] for s in says)
    session_id = next(e["session_id"] for e in events if e["type"] == "session")

    # Identical text: the concatenation of spoken sentences equals what was
    # persisted (and is exactly what was sent to TTS).
    hist = client.get(f"/api/history/{session_id}").json()
    user_msgs = [m for m in hist["messages"] if m["role"] == "user"]
    assistant_msgs = [m for m in hist["messages"] if m["role"] == "assistant"]
    assert user_msgs[-1]["content"] == transcript
    assert user_msgs[-1]["input_type"] == "voice"
    assert assistant_msgs[-1]["content"] == answer


def test_voice_text_path_is_spoken() -> None:
    with client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["type"] == "info"
        ws.send_json({"type": "message", "message": "hello over voice", "session_id": None})
        events = _drain(ws)
    types = [e["type"] for e in events]
    says = [e for e in events if e["type"] == "say"]
    assert "say" in types and types[-1] == "done"
    assert any(s["audio"] for s in says)  # each spoken sentence carries audio


def test_interrupt_keeps_socket_healthy() -> None:
    with client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["type"] == "info"
        ws.send_json({"type": "message", "message": "first question", "session_id": None})
        ws.send_json({"type": "interrupt"})
        # Drain whatever came back for the (possibly interrupted) first turn.
        first = _drain_lenient(ws)
        assert first is not None
        # Socket still works: a fresh turn completes normally.
        ws.send_json({"type": "message", "message": "second question", "session_id": None})
        events = _drain(ws)
        assert events[-1]["type"] == "done"


def _drain_lenient(ws) -> list[dict] | None:
    """Read until a terminal event, tolerating an 'interrupted' info."""
    events = []
    for _ in range(200):
        e = ws.receive_json()
        events.append(e)
        if e["type"] in ("done", "error"):
            return events
        if e["type"] == "info" and e.get("message") == "interrupted":
            return events
    return events
