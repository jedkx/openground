from __future__ import annotations

import pytest
from openground.services.state_machine import StateMachine, SystemState


def test_initial_state_is_boot() -> None:
    sm = StateMachine(5.0)
    assert sm.state == SystemState.BOOT


def test_client_connect_moves_to_connecting() -> None:
    sm = StateMachine(5.0)
    sm.on_client_connected()
    assert sm.state == SystemState.CONNECTING


def test_packet_received_moves_to_nominal() -> None:
    sm = StateMachine(5.0)
    sm.on_client_connected()
    sm.on_packet_received()
    assert sm.state == SystemState.NOMINAL


def test_lost_after_disconnect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    sm = StateMachine(1.0)
    sm.on_client_connected()
    t0 = 1_000_000.0
    monkeypatch.setattr("openground.services.state_machine.time.time", lambda: t0)
    sm.on_client_disconnected(0)
    monkeypatch.setattr("openground.services.state_machine.time.time", lambda: t0 + 2.0)
    sm.check_timeout()
    assert sm.state == SystemState.LOST


def test_lost_after_data_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    sm = StateMachine(1.0)
    sm.on_client_connected()
    t0 = 1_000_000.0
    monkeypatch.setattr("openground.services.state_machine.time.time", lambda: t0)
    sm.on_packet_received()
    monkeypatch.setattr("openground.services.state_machine.time.time", lambda: t0 + 2.0)
    sm.check_timeout()
    assert sm.state == SystemState.LOST
