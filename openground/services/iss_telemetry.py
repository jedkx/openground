"""Fetch live ISS state from the public Where The ISS At? HTTP API (third-party, not NASA)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from openground.services.simulator import format_met_hhmmss

log = logging.getLogger(__name__)


def parse_iss_json(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize API JSON into OpenGround telemetry scalars + extras.

    Documented field shapes: https://wheretheiss.at/w/developer (latitude, longitude,
    altitude in km, velocity in km/s, timestamp unix seconds).
    """
    lat = float(data["latitude"])
    lon = float(data["longitude"])
    alt_km = float(data["altitude"])
    vel_kms = float(data["velocity"])
    footprint = data.get("footprint")
    visibility = data.get("visibility")
    ts = data.get("timestamp")
    epoch_ms: int
    if isinstance(ts, (int, float)) and float(ts) > 1e9:
        epoch_ms = int(float(ts) * 1000)
    else:
        epoch_ms = int(time.time() * 1000)
    out: dict[str, Any] = {
        "altitude": round(alt_km * 1000.0, 2),
        "velocity": round(vel_kms * 1000.0, 2),
        "temperature": 20.0,
        "battery": 99.0,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "phase": "ISS_PUBLIC",
        "epoch_ms": epoch_ms,
        "timestamp": time.strftime("%H:%M:%S", time.gmtime(epoch_ms / 1000.0)),
        "iss_footprint_km": (
            round(float(footprint), 2) if isinstance(footprint, (int, float)) else None
        ),
        "iss_visibility": visibility if isinstance(visibility, str) else None,
    }
    return out


async def fetch_iss_state(client: httpx.AsyncClient, url: str) -> dict[str, Any] | None:
    try:
        r = await client.get(url)
        r.raise_for_status()
        body = r.json()
        if not isinstance(body, dict):
            return None
        return parse_iss_json(body)
    except (httpx.HTTPError, OSError, KeyError, TypeError, ValueError) as e:
        log.warning("ISS API fetch failed: %s", e)
        return None


def finalize_iss_packet(
    base: dict[str, Any],
    *,
    mission_start_epoch_ms: int,
) -> dict[str, Any]:
    """Attach MET fields derived from sample epoch."""
    epoch_ms = int(base["epoch_ms"])
    met_ms = max(0, epoch_ms - mission_start_epoch_ms)
    packet: dict[str, Any] = {
        **base,
        "mission_start_epoch_ms": mission_start_epoch_ms,
        "met_ms": met_ms,
        "met_hhmmss": format_met_hhmmss(met_ms),
        "mission_event": "ISS (NORAD 25544) — public API snapshot",
    }
    if packet.get("iss_footprint_km") is None:
        packet.pop("iss_footprint_km", None)
    if packet.get("iss_visibility") is None:
        packet.pop("iss_visibility", None)
    return packet
