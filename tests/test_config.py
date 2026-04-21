"""Configuration defaults and environment overrides."""

from __future__ import annotations

import pytest
from openground.config import load_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "OPENGROUND_TELEMETRY_HZ",
        "OPENGROUND_LINK_DROP_PROB",
        "OPENGROUND_HISTORY_MAX",
        "OPENGROUND_LOST_TIMEOUT_S",
        "OPENGROUND_SCENARIO",
        "OPENGROUND_TELEMETRY_MODE",
        "OPENGROUND_MILESTONE_TIMELINE_PATH",
        "OPENGROUND_ARTEMIS_TIMELINE_PATH",
        "OPENGROUND_ISS_API_URL",
        "OPENGROUND_STATIC_DIR",
        "OPENGROUND_OPENMCT_DIST",
        "OPENGROUND_LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)

    s = load_settings()
    assert s.telemetry_hz == 1.0
    assert s.telemetry_period_s == 1.0
    assert s.link_drop_probability == 0.08
    assert s.history_maxlen == 5000
    assert s.simulation_scenario == "nominal"
    assert s.telemetry_mode == "sim"
    assert s.milestone_timeline_path == ""
    assert "wheretheiss" in s.iss_api_url


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENGROUND_TELEMETRY_HZ", "2")
    monkeypatch.setenv("OPENGROUND_HISTORY_MAX", "100")
    monkeypatch.setenv("OPENGROUND_SCENARIO", "gentle")
    monkeypatch.setenv("OPENGROUND_TELEMETRY_MODE", "milestone_replay")
    monkeypatch.setenv("OPENGROUND_MILESTONE_TIMELINE_PATH", "/tmp/custom_milestones.json")
    monkeypatch.setenv("OPENGROUND_ISS_API_URL", "https://example.invalid/iss")
    s = load_settings()
    assert s.telemetry_hz == 2.0
    assert s.telemetry_period_s == 0.5
    assert s.history_maxlen == 100
    assert s.simulation_scenario == "gentle"
    assert s.telemetry_mode == "milestone_replay"
    assert s.milestone_timeline_path == "/tmp/custom_milestones.json"
    assert s.iss_api_url == "https://example.invalid/iss"


def test_legacy_artemis_mode_and_path_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENGROUND_TELEMETRY_MODE", "artemis_timeline")
    monkeypatch.setenv("OPENGROUND_ARTEMIS_TIMELINE_PATH", "/tmp/legacy.json")
    s = load_settings()
    assert s.telemetry_mode == "milestone_replay"
    assert s.milestone_timeline_path == "/tmp/legacy.json"


def test_unknown_scenario_string_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENGROUND_SCENARIO", "does-not-exist")
    s = load_settings()
    assert s.simulation_scenario == "does-not-exist"
