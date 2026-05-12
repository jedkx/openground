"""Envelope adapter behavior tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from openground.application import create_app


def test_envelope_accepts_external_event_id() -> None:
    client = TestClient(create_app())
    r = client.post(
        "/api/missions/raspberry-pi/adapters/envelope",
        json={
            "external_event_id": "evt-101",
            "event_type": "telemetry.normalized",
            "payload": {
                "altitude": 120.0,
                "velocity": 30.0,
                "temperature": 22.0,
                "battery": 95.0,
                "lat": 39.9,
                "lon": 32.8,
                "source": "sentinel-pi-01",
            },
        },
    )
    assert r.status_code == 202
    body = r.json()
    assert body["adapter"] == "envelope"
    assert body["status"] == "accepted"


def test_envelope_accepts_relay_compat_alias() -> None:
    client = TestClient(create_app())
    r = client.post(
        "/api/missions/raspberry-pi/adapters/envelope",
        json={
            "relay_event_id": "evt-compat-1",
            "event_type": "telemetry.normalized",
            "payload": {
                "temperature": 20.0,
                "ram_usage": 55.0,
            },
        },
    )
    assert r.status_code == 202
    body = r.json()
    assert body["adapter"] == "envelope"
    assert body["status"] == "accepted"
