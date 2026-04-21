"""Envelope adapter behavior tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from openground.application import create_app


def test_envelope_accepts_external_event_id(monkeypatch) -> None:
    monkeypatch.setenv("OPENGROUND_TELEMETRY_HZ", "1e-12")
    client = TestClient(create_app())
    r = client.post(
        "/api/v1/adapters/envelope",
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
    latest = client.get("/api/openmct/telemetry/latest").json()["data"]
    assert latest["sim"]["external_event_id"] == "evt-101"


def test_envelope_accepts_relay_compat_alias(monkeypatch) -> None:
    monkeypatch.setenv("OPENGROUND_TELEMETRY_HZ", "1e-12")
    client = TestClient(create_app())
    r = client.post(
        "/api/v1/adapters/envelope",
        json={
            "relay_event_id": "evt-compat-1",
            "event_type": "telemetry.normalized",
            "payload": {
                "altitude": 100.0,
                "velocity": 10.0,
                "temperature": 20.0,
                "battery": 90.0,
                "lat": 39.0,
                "lon": 32.0,
            },
        },
    )
    assert r.status_code == 202
