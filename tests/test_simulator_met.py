"""Mission elapsed time fields from simulator."""

from __future__ import annotations

from openground.services.simulator import FlightPhase, TelemetrySimulator, format_met_hhmmss


def test_format_met_hhmmss() -> None:
    assert format_met_hhmmss(0) == "00:00:00"
    assert format_met_hhmmss(61_000) == "00:01:01"
    assert format_met_hhmmss(3_600_000) == "01:00:00"


def test_step_includes_met_keys() -> None:
    sim = TelemetrySimulator()
    row = sim.step(1.0)
    assert "mission_start_epoch_ms" in row
    assert "met_ms" in row
    assert "met_hhmmss" in row
    assert isinstance(row["met_ms"], int)
    assert row["met_ms"] >= 0


def test_new_mission_resets_t0_on_launch_cycle() -> None:
    sim = TelemetrySimulator()
    sim.phase = FlightPhase.LANDED
    sim.phase_elapsed_s = sim.profile.t_landed_s
    sim.step(0.5)
    assert sim.phase == FlightPhase.LAUNCH
    assert sim.phase_elapsed_s == 0.0
    assert sim.battery == 100.0
    assert sim.mission_start_epoch_ms > 0
