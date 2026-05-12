from __future__ import annotations

import struct

import pytest
from openground.ccsds import APID_TELEMETRY, parse_packet


def _make_packet(apid: int = APID_TELEMETRY, seq: int = 0, payload: bytes = b"\x00" * 4) -> bytes:
    word1 = (0b000 << 13) | (0 << 12) | (0 << 11) | apid
    word2 = (0b11 << 14) | (seq & 0x3FFF)
    word3 = len(payload) - 1
    return struct.pack(">HHH", word1, word2, word3) + payload


def test_parse_header_fields() -> None:
    raw = _make_packet(seq=0x3FFF)
    parsed = parse_packet(raw)
    assert parsed["header"]["apid"] == APID_TELEMETRY
    assert parsed["header"]["seq_count"] == 0x3FFF


def test_parse_returns_raw_data_bytes() -> None:
    payload = b"\xDE\xAD\xBE\xEF"
    raw = _make_packet(payload=payload)
    assert parse_packet(raw)["data"] == payload


def test_parse_rejects_short_buffer() -> None:
    with pytest.raises(ValueError, match="too short"):
        parse_packet(b"\x00\x01")
