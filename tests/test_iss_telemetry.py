"""ISS public API parsing."""

from __future__ import annotations

import pytest
from openground.services.iss_telemetry import finalize_iss_packet, parse_iss_json


def test_parse_iss_json_converts_units() -> None:
    raw = {
        "latitude": 12.34,
        "longitude": -56.78,
        "altitude": 400.0,
        "velocity": 7.66,
        "footprint": 4500.0,
        "visibility": "daylight",
        "timestamp": 1700000000.0,
    }
    p = parse_iss_json(raw)
    assert p["altitude"] == pytest.approx(400_000.0, rel=1e-9)
    assert p["velocity"] == pytest.approx(7660.0, rel=1e-9)
    assert p["lat"] == pytest.approx(12.34, rel=1e-9)
    assert p["lon"] == pytest.approx(-56.78, rel=1e-9)
    assert p["iss_footprint_km"] == pytest.approx(4500.0)
    assert p["iss_visibility"] == "daylight"
    assert p["epoch_ms"] == 1_700_000_000_000


def test_finalize_iss_packet_met() -> None:
    base = parse_iss_json(
        {
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 400.0,
            "velocity": 7.66,
            "timestamp": 1000.0,
        }
    )
    out = finalize_iss_packet(base, mission_start_epoch_ms=500_000)
    assert out["met_ms"] == int(base["epoch_ms"]) - 500_000
    assert "met_hhmmss" in out
