"""Ground state machine transitions."""

from __future__ import annotations

import pytest
from openground.services.state_machine import StateMachine, SystemState


def test_connect_moves_boot_to_connecting() -> None:
    sm = StateMachine(5.0)
    assert sm.state == SystemState.BOOT
    sm.on_client_connected()
    assert sm.state == SystemState.CONNECTING


def test_nominal_when_healthy() -> None:
    sm = StateMachine(5.0)
    sm.on_client_connected()
    sm.on_packet_sent({"battery": 50.0, "temperature": 25.0})
    assert sm.state == SystemState.NOMINAL


def test_degraded_low_battery() -> None:
    sm = StateMachine(5.0)
    sm.on_client_connected()
    sm.on_packet_sent({"battery": 10.0, "temperature": 25.0})
    assert sm.state == SystemState.DEGRADED


def test_degraded_high_temperature() -> None:
    sm = StateMachine(5.0)
    sm.on_client_connected()
    sm.on_packet_sent({"battery": 50.0, "temperature": 85.0})
    assert sm.state == SystemState.DEGRADED


def test_lost_after_disconnect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    sm = StateMachine(1.0)
    sm.on_client_connected()
    t0 = 1_000_000.0
    monkeypatch.setattr("openground.services.state_machine.time.time", lambda: t0)
    sm.on_client_disconnected(0)
    monkeypatch.setattr("openground.services.state_machine.time.time", lambda: t0 + 2.0)
    sm.check_timeout()
    assert sm.state == SystemState.LOST
