"""CCSDS-like framing: build/parse round-trip and invariants."""

from __future__ import annotations

import pytest
from openground.ccsds import APID_TELEMETRY, build_packet, parse_packet


def test_build_parse_roundtrip() -> None:
    data = {
        "altitude": 123.45,
        "velocity": 10.0,
        "temperature": 20.0,
        "battery": 99.0,
        "lat": 40.0,
        "lon": 30.0,
    }
    raw = build_packet(data, 0x3FFF)
    parsed = parse_packet(raw)

    assert parsed["header"]["apid"] == APID_TELEMETRY
    assert parsed["header"]["seq_count"] == 0x3FFF
    assert parsed["data"]["altitude"] == pytest.approx(123.45)
    assert len(raw) == 30


def test_parse_rejects_short_buffer() -> None:
    with pytest.raises(ValueError, match="too short"):
        parse_packet(b"\x00\x01")
