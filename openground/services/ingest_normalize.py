"""Map external ingest payloads into the same telemetry envelope used by the internal sim."""

from __future__ import annotations

import time
from typing import Any

from openground.services.simulator import format_met_hhmmss

_KNOWN_OPTIONAL_NUMERIC = frozenset(
    {
        "mission_event",
        "met_phase_index",
        "accel_proxy_mps2",
        "earth_range_km",
        "moon_range_km",
    }
)
_ROUTING_KEYS = frozenset({"source", "ingress_id"})


def normalized_http_fields_to_telemetry(fields: dict[str, Any]) -> dict[str, Any]:
    """Merge flat HTTP JSON (six CCSDS scalars + optional MET) into a display-ready packet dict."""
    now_ms = int(time.time() * 1000)
    epoch = int(fields["epoch_ms"]) if fields.get("epoch_ms") is not None else now_ms
    ms_start = (
        int(fields["mission_start_epoch_ms"])
        if fields.get("mission_start_epoch_ms") is not None
        else epoch
    )
    met_ms = max(0, epoch - ms_start)
    out: dict[str, Any] = {
        "altitude": round(float(fields["altitude"]), 2),
        "velocity": round(float(fields["velocity"]), 2),
        "temperature": round(float(fields["temperature"]), 2),
        "battery": round(float(fields["battery"]), 2),
        "lat": round(float(fields["lat"]), 6),
        "lon": round(float(fields["lon"]), 6),
        "phase": str(fields["phase"]) if fields.get("phase") is not None else "INGEST",
        "epoch_ms": epoch,
        "timestamp": time.strftime("%H:%M:%S"),
        "mission_start_epoch_ms": ms_start,
        "met_ms": met_ms,
        "met_hhmmss": format_met_hhmmss(met_ms),
    }
    for k in _KNOWN_OPTIONAL_NUMERIC:
        if k in fields and fields[k] is not None:
            out[k] = fields[k]
    reserved = frozenset(out.keys()) | _ROUTING_KEYS
    for k, v in fields.items():
        if k not in reserved and v is not None:
            out[k] = v
    return out


def telemetry_from_parsed_wire_packet(parsed: dict[str, Any], *, now_ms: int) -> dict[str, Any]:
    """Attach ground-side timestamps to CCSDS data-field values from :func:`openground.ccsds.parse_packet`."""
    return {
        **parsed["data"],
        "phase": "EXTERNAL",
        "epoch_ms": now_ms,
        "timestamp": time.strftime("%H:%M:%S"),
        "mission_start_epoch_ms": now_ms,
        "met_ms": 0,
        "met_hhmmss": format_met_hhmmss(0),
    }
