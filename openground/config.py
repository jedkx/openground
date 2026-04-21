"""Environment-driven configuration (12-Factor style; no secrets in code)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _default_milestone_timeline_path() -> str:
    base = Path(__file__).resolve().parent.parent
    return str(base / "data" / "demo_documented_milestones.json")


@dataclass(frozen=True, slots=True)
class Settings:
    """Operational parameters for the ground data system."""

    telemetry_hz: float
    link_drop_probability: float
    history_maxlen: int
    lost_timeout_seconds: float
    simulation_scenario: str
    static_dir: str
    openmct_dist_dir: str
    log_level: str
    telemetry_mode: str
    milestone_timeline_path: str
    iss_api_url: str
    ingest_enabled: bool
    """When False, HTTP ingest routes return 503 (simulation-only ground)."""

    ingest_token: str
    """When non-empty, ingest endpoints require matching Bearer or X-Ingest-Token."""

    database_url: str
    """When non-empty, finalized frames are archived to Postgres; history API reads from it."""

    @property
    def telemetry_period_s(self) -> float:
        if self.telemetry_hz <= 0:
            return 1.0
        return 1.0 / self.telemetry_hz


def load_settings() -> Settings:
    timeline_override = os.environ.get("OPENGROUND_MILESTONE_TIMELINE_PATH") or os.environ.get(
        "OPENGROUND_ARTEMIS_TIMELINE_PATH"
    )
    milestone_path = (
        str(Path(timeline_override).expanduser())
        if timeline_override and timeline_override.strip()
        else _default_milestone_timeline_path()
    )
    mode_raw = _env_str("OPENGROUND_TELEMETRY_MODE", "sim").strip().lower()
    if mode_raw == "artemis_timeline":
        mode_raw = "milestone_replay"
    iss_url = os.environ.get("OPENGROUND_ISS_API_URL")
    iss_api = (
        str(iss_url).strip()
        if iss_url and str(iss_url).strip()
        else "https://api.wheretheiss.at/v1/satellites/25544"
    )
    ingest_disabled_raw = os.environ.get("OPENGROUND_INGEST_DISABLED", "")
    ingest_enabled = str(ingest_disabled_raw).strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    )

    return Settings(
        telemetry_hz=_env_float("OPENGROUND_TELEMETRY_HZ", 1.0),
        link_drop_probability=_env_float("OPENGROUND_LINK_DROP_PROB", 0.08),
        history_maxlen=_env_int("OPENGROUND_HISTORY_MAX", 5000),
        lost_timeout_seconds=_env_float("OPENGROUND_LOST_TIMEOUT_S", 5.0),
        simulation_scenario=_env_str("OPENGROUND_SCENARIO", "nominal"),
        static_dir=_env_str("OPENGROUND_STATIC_DIR", "static"),
        openmct_dist_dir=_env_str("OPENGROUND_OPENMCT_DIST", "node_modules/openmct/dist"),
        log_level=_env_str("OPENGROUND_LOG_LEVEL", "INFO"),
        telemetry_mode=mode_raw,
        milestone_timeline_path=milestone_path,
        iss_api_url=iss_api,
        ingest_enabled=ingest_enabled,
        ingest_token=_env_str("OPENGROUND_INGEST_TOKEN", ""),
        database_url=_env_str("OPENGROUND_DATABASE_URL", ""),
    )
