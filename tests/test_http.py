"""HTTP surface smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from openground.application import create_app


def test_health() -> None:
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_status_shape() -> None:
    client = TestClient(create_app())
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "openground"
    assert "websocket_clients" in body
    assert "system_state" in body


def test_openmct_latest() -> None:
    client = TestClient(create_app())
    r = client.get("/api/openmct/telemetry/latest")
    assert r.status_code == 200
    assert "data" in r.json()


def test_openmct_history_accepts_float_bounds() -> None:
    client = TestClient(create_app())
    r = client.get("/api/openmct/telemetry/history", params={"start": 1.5, "end": 10.5})
    assert r.status_code == 200
    assert "data" in r.json()
