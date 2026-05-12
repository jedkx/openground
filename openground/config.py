"""Environment-driven configuration (12-Factor style; no secrets in code).

``missions.toml`` is the primary mission source.  Legacy env-var settings
remain so that existing deployments continue to work without changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from openground.constants import (
    DEFAULT_HISTORY_MAXLEN,
    DEFAULT_LOST_TIMEOUT_SECONDS,
)


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


@dataclass(frozen=True, slots=True)
class Settings:
    """Operational parameters for the ground data system."""

    static_dir: str
    openmct_dist_dir: str
    log_level: str

    missions_file: str
    """Path to missions.toml.  When absent the legacy env-var fields below
    are used to synthesise a single default mission."""

    # --- legacy single-mission env vars ---
    history_maxlen: int
    lost_timeout_seconds: float
    ingest_token: str
    database_url: str


def load_settings() -> Settings:
    return Settings(
        static_dir=_env_str("OPENGROUND_STATIC_DIR", "static"),
        openmct_dist_dir=_env_str("OPENGROUND_OPENMCT_DIST", "node_modules/openmct/dist"),
        log_level=_env_str("OPENGROUND_LOG_LEVEL", "INFO"),
        missions_file=_env_str("OPENGROUND_MISSIONS_FILE", "missions.toml"),
        history_maxlen=_env_int("OPENGROUND_HISTORY_MAX", DEFAULT_HISTORY_MAXLEN),
        lost_timeout_seconds=_env_float("OPENGROUND_LOST_TIMEOUT_S", DEFAULT_LOST_TIMEOUT_SECONDS),
        ingest_token=_env_str("OPENGROUND_INGEST_TOKEN", ""),
        database_url=_env_str("OPENGROUND_DATABASE_URL", ""),
    )
