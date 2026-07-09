"""API tests for Phase 2: request-id header, health probes, error envelope."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError, register_exception_handlers
from app.core.middleware import RequestContextMiddleware
from app.main import app

client = TestClient(app)


def test_request_id_header_present() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")


def test_inbound_request_id_is_echoed() -> None:
    resp = client.get("/api/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers.get("X-Request-ID") == "abc123"


def test_liveness_and_readiness() -> None:
    assert client.get("/api/health/live").json() == {"status": "ok"}
    ready = client.get("/api/health/ready")
    # In stub mode nothing is unreachable, so readiness is ok.
    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"


def test_error_envelope_shape() -> None:
    """A raised AppError is rendered as the standard error envelope."""
    tmp = FastAPI()
    tmp.add_middleware(RequestContextMiddleware)
    register_exception_handlers(tmp)

    @tmp.get("/boom")
    async def boom() -> None:
        raise NotFoundError("nope", details={"id": 1})

    tmp_client = TestClient(tmp)
    resp = tmp_client.get("/boom")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "nope"
    assert body["error"]["details"] == {"id": 1}
    assert "request_id" in body["error"]
