"""Mission configuration: TOML-driven, one file per deployment.

``missions.toml`` declares every mission and its ingest token.  When the file
is absent or empty the loader falls back to a single default mission built from
environment variables so existing deployments continue to work unchanged.

TOML format::

    [[missions]]
    id   = "raspberry-pi"
    name = "Raspberry Pi"
    [missions.adapter]
    type  = "http_ingest"
    token = "secret"
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openground.sdk.channel import ChannelSpec

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HttpIngestAdapterConfig:
    type: str = "http_ingest"
    token: str = ""


AdapterConfig = HttpIngestAdapterConfig


# ---------------------------------------------------------------------------
# Top-level mission configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MissionConfig:
    id: str
    name: str
    adapter: AdapterConfig
    channels: tuple[ChannelSpec, ...] = field(default_factory=tuple)
    history_maxlen: int = 5_000
    lost_timeout_seconds: float = 5.0
    database_url: str = ""


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_adapter(raw: dict[str, Any]) -> AdapterConfig:
    return HttpIngestAdapterConfig(token=str(raw.get("token", "")))


def _parse_channel(raw: dict[str, Any]) -> ChannelSpec:
    return ChannelSpec(
        id=str(raw["id"]),
        unit=str(raw.get("unit", "")),
        min_val=float(raw["min"]) if "min" in raw else None,
        max_val=float(raw["max"]) if "max" in raw else None,
        description=str(raw.get("description", "")),
    )


def _parse_mission(raw: dict[str, Any]) -> MissionConfig:
    mission_id = str(raw["id"]).strip()
    if not mission_id:
        raise ValueError("Mission 'id' must be a non-empty string")
    channels = tuple(_parse_channel(c) for c in raw.get("channels", []))
    return MissionConfig(
        id=mission_id,
        name=str(raw.get("name", mission_id)),
        adapter=_parse_adapter(raw.get("adapter", {})),
        channels=channels,
        history_maxlen=int(raw.get("history_maxlen", 5_000)),
        lost_timeout_seconds=float(raw.get("lost_timeout_seconds", 5.0)),
        database_url=str(raw.get("database_url", "")),
    )


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def load_missions_file(path: str) -> list[MissionConfig]:
    """Parse ``missions.toml`` and return a list of :class:`MissionConfig`.

    Returns an empty list (not an error) when the file does not exist,
    allowing the caller to fall back to env-var defaults.
    """
    p = Path(path)
    if not p.is_file():
        log.debug("No missions file at %s; using env-var defaults", p.resolve())
        return []
    with p.open("rb") as fh:
        data = tomllib.load(fh)
    missions_raw: list[dict[str, Any]] = data.get("missions", [])
    configs: list[MissionConfig] = []
    for raw in missions_raw:
        try:
            configs.append(_parse_mission(raw))
        except Exception:
            log.exception("Skipping malformed mission entry: %r", raw.get("id", "<unknown>"))
    return configs
