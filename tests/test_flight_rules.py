"""Flight rules evaluation."""

from __future__ import annotations

from openground.services.flight_rules import evaluate_flight_rules


def test_no_violations_nominal() -> None:
    p = {
        "battery": 50.0,
        "temperature": 25.0,
        "system_state": "NOMINAL",
        "ccsds": {"loss_rate": 0.0},
    }
    assert evaluate_flight_rules(p) == []


def test_battery_critical() -> None:
    p = {
        "battery": 10.0,
        "temperature": 25.0,
        "system_state": "NOMINAL",
        "ccsds": {"loss_rate": 0.0},
    }
    v = evaluate_flight_rules(p)
    assert any(x["id"] == "FR-BATT-CRIT" for x in v)


def test_battery_warning_only() -> None:
    p = {
        "battery": 20.0,
        "temperature": 25.0,
        "system_state": "NOMINAL",
        "ccsds": {"loss_rate": 0.0},
    }
    v = evaluate_flight_rules(p)
    ids = {x["id"] for x in v}
    assert "FR-BATT-WARN" in ids
    assert "FR-BATT-CRIT" not in ids


def test_ground_lost() -> None:
    p = {
        "battery": 50.0,
        "temperature": 25.0,
        "system_state": "LOST",
        "ccsds": {"loss_rate": 0.0},
    }
    v = evaluate_flight_rules(p)
    assert any(x["id"] == "FR-GROUND-LOST" for x in v)
