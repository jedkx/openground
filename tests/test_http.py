"""HTTP surface smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_status_shape() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "openground"
    assert "websocket_clients" in body
    assert "system_state" in body


def test_openmct_latest() -> None:
    client = TestClient(app)
    r = client.get("/api/openmct/telemetry/latest")
    assert r.status_code == 200
    assert "data" in r.json()
