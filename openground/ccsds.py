"""CCSDS Space Packet Protocol header framing (simplified primary header only)."""

from __future__ import annotations

import struct

CCSDS_VERSION = 0b000
PACKET_TYPE_TLM = 0
SEC_HDR_FLAG = 0
APID_TELEMETRY = 0x064
SEQ_FLAG_UNSEG = 0b11
SEQ_MASK = 0x3FFF  # 14-bit CCSDS sequence counter wraps at 16383


def parse_packet(raw: bytes) -> dict:
    if len(raw) < 6:
        raise ValueError(f"Packet too short: {len(raw)} bytes")

    word1, word2, word3 = struct.unpack(">HHH", raw[:6])

    return {
        "header": {
            "version": (word1 >> 13) & 0x07,
            "type": (word1 >> 12) & 0x01,
            "apid": word1 & 0x07FF,
            "seq_flags": (word2 >> 14) & 0x03,
            "seq_count": word2 & SEQ_MASK,
            "length": word3,
        },
        "data": raw[6:],
    }
