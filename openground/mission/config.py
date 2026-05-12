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

    # optional tuning
    [missions.pipeline]
    ingest_queue_maxsize = 500
    worker_queue_maxsize = 1000

    [missions.storage]
    pool_min_size = 1
    pool_max_size = 8
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


from openground.sdk.channel import ChannelSpec
from openground.constants import (
    DEFAULT_INGEST_QUEUE_MAXSIZE,
    DEFAULT_WORKER_QUEUE_MAXSIZE,
    DEFAULT_LOST_TIMEOUT_SECONDS,
    DEFAULT_HISTORY_MAXLEN,
)

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
# Pipeline + Storage tuning
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    ingest_queue_maxsize: int = DEFAULT_INGEST_QUEUE_MAXSIZE
    worker_queue_maxsize: int = DEFAULT_WORKER_QUEUE_MAXSIZE
    timeout_check_interval_seconds: float = 1.0


@dataclass(frozen=True, slots=True)
class StorageConfig:
    pool_min_size: int = 1
    pool_max_size: int = 8
    query_default_limit: int = 50_000
    query_max_limit: int = 200_000


# ---------------------------------------------------------------------------
# Top-level mission configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MissionConfig:
    id: str
    name: str
    adapter: AdapterConfig
    channels: tuple[ChannelSpec, ...] = field(default_factory=tuple)
    history_maxlen: int = DEFAULT_HISTORY_MAXLEN
    lost_timeout_seconds: float = DEFAULT_LOST_TIMEOUT_SECONDS
    database_url: str = ""
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_adapter(raw: dict[str, Any]) -> AdapterConfig:
    return HttpIngestAdapterConfig(token=str(raw.get("token", "")))


def _parse_channel(raw: dict[str, Any]) -> ChannelSpec:
    # Parse severity and rules if present
    severity = str(raw.get("severity", "warning"))
    rules = tuple(raw.get("rules", ()))
    # Accept comma-separated string for rules as well
    if isinstance(rules, str):
        rules = tuple(r.strip() for r in rules.split(",") if r.strip())
    return ChannelSpec(
        id=str(raw["id"]),
        unit=str(raw.get("unit", "")),
        min_val=float(raw["min"]) if "min" in raw else None,
        max_val=float(raw["max"]) if "max" in raw else None,
        description=str(raw.get("description", "")),
        severity=severity,
        rules=rules,
    )


def _parse_pipeline(raw: dict[str, Any]) -> PipelineConfig:
    return PipelineConfig(
        ingest_queue_maxsize=int(raw.get("ingest_queue_maxsize", DEFAULT_INGEST_QUEUE_MAXSIZE)),
        worker_queue_maxsize=int(raw.get("worker_queue_maxsize", DEFAULT_WORKER_QUEUE_MAXSIZE)),
        timeout_check_interval_seconds=float(raw.get("timeout_check_interval_seconds", 1.0)),
    )


def _parse_storage(raw: dict[str, Any]) -> StorageConfig:
    return StorageConfig(
        pool_min_size=int(raw.get("pool_min_size", 1)),
        pool_max_size=int(raw.get("pool_max_size", 8)),
        query_default_limit=int(raw.get("query_default_limit", 50_000)),
        query_max_limit=int(raw.get("query_max_limit", 200_000)),
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
        pipeline=_parse_pipeline(raw.get("pipeline", {})),
        storage=_parse_storage(raw.get("storage", {})),
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
