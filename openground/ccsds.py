"""CCSDS Space Packet Protocol–style framing for telemetry (simplified)."""

from __future__ import annotations

import struct

CCSDS_VERSION = 0b000
PACKET_TYPE_TLM = 0
SEC_HDR_FLAG = 0
APID_TELEMETRY = 0x064
SEQ_FLAG_UNSEG = 0b11


def build_packet(data: dict, sequence_count: int) -> bytes:
    """Build a CCSDS-like telemetry packet from normalized telemetry fields."""
    data_field = struct.pack(
        ">ffffff",
        float(data["altitude"]),
        float(data["velocity"]),
        float(data["temperature"]),
        float(data["battery"]),
        float(data["lat"]),
        float(data["lon"]),
    )

    packet_length = len(data_field) - 1
    word1 = (CCSDS_VERSION << 13) | (PACKET_TYPE_TLM << 12) | (SEC_HDR_FLAG << 11) | APID_TELEMETRY

    seq_count = sequence_count & 0x3FFF
    word2 = (SEQ_FLAG_UNSEG << 14) | seq_count
    word3 = packet_length

    primary_header = struct.pack(">HHH", word1, word2, word3)
    return primary_header + data_field


def parse_packet(raw: bytes) -> dict:
    """Parse a CCSDS-like telemetry packet into structured header/data fields."""
    if len(raw) < 6:
        raise ValueError(f"Packet too short: {len(raw)}")

    word1, word2, word3 = struct.unpack(">HHH", raw[:6])

    version = (word1 >> 13) & 0x07
    packet_type = (word1 >> 12) & 0x01
    apid = word1 & 0x07FF
    seq_flags = (word2 >> 14) & 0x03
    seq_count = word2 & 0x3FFF
    packet_length = word3

    data_raw = raw[6:]
    if len(data_raw) < 24:
        raise ValueError(f"Data field too short: {len(data_raw)}")

    altitude, velocity, temperature, battery, lat, lon = struct.unpack(">ffffff", data_raw[:24])

    return {
        "header": {
            "version": version,
            "type": packet_type,
            "apid": apid,
            "seq_flags": seq_flags,
            "seq_count": seq_count,
            "length": packet_length,
        },
        "data": {
            "altitude": round(altitude, 2),
            "velocity": round(velocity, 2),
            "temperature": round(temperature, 2),
            "battery": round(battery, 2),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        },
    }
