"""Configuration defaults and environment overrides."""

from __future__ import annotations

import pytest
from openground.config import load_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "OPENGROUND_HISTORY_MAX",
        "OPENGROUND_LOST_TIMEOUT_S",
        "OPENGROUND_STATIC_DIR",
        "OPENGROUND_OPENMCT_DIST",
        "OPENGROUND_LOG_LEVEL",
        "OPENGROUND_INGEST_TOKEN",
        "OPENGROUND_DATABASE_URL",
        "OPENGROUND_MISSIONS_FILE",
    ):
        monkeypatch.delenv(key, raising=False)

    s = load_settings()
    assert s.history_maxlen == 5000
    assert s.lost_timeout_seconds == 5.0
    assert s.log_level == "INFO"
    assert s.ingest_token == ""
    assert s.database_url == ""
    assert s.missions_file == "missions.toml"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENGROUND_HISTORY_MAX", "100")
    monkeypatch.setenv("OPENGROUND_LOST_TIMEOUT_S", "10.0")
    monkeypatch.setenv("OPENGROUND_INGEST_TOKEN", "secret")
    monkeypatch.setenv("OPENGROUND_DATABASE_URL", "postgresql://localhost/og")
    s = load_settings()
    assert s.history_maxlen == 100
    assert s.lost_timeout_seconds == 10.0
    assert s.ingest_token == "secret"
    assert s.database_url == "postgresql://localhost/og"
