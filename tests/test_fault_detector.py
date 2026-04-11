"""Plausibility rules."""

from __future__ import annotations

from openground.services.fault_detector import FaultDetector


def test_altitude_below_zero() -> None:
    fd = FaultDetector()
    faults = fd.check(
        {
            "altitude": -1.0,
            "velocity": 0.0,
            "temperature": 20.0,
            "battery": 50.0,
        }
    )
    assert any("Altitude below zero" in f for f in faults)


def test_battery_out_of_range() -> None:
    fd = FaultDetector()
    faults = fd.check(
        {
            "altitude": 0.0,
            "velocity": 0.0,
            "temperature": 20.0,
            "battery": 101.0,
        }
    )
    assert any("Battery out of range" in f for f in faults)


def test_reset_clears_altitude_history() -> None:
    fd = FaultDetector()
    fd.check({"altitude": 100_000.0, "velocity": 1.0, "temperature": 20.0, "battery": 50.0})
    fd.reset()
    faults = fd.check({"altitude": 0.0, "velocity": 50.0, "temperature": 20.0, "battery": 50.0})
    assert not any("Altitude change" in f for f in faults)
