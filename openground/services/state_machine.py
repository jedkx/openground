"""Ground-side link and vehicle health state (not flight software)."""

from __future__ import annotations

import logging
import time
from enum import StrEnum

log = logging.getLogger(__name__)


class SystemState(StrEnum):
    BOOT = "BOOT"
    CONNECTING = "CONNECTING"
    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    LOST = "LOST"


class StateMachine:
    """Models operator-visible comms and coarse vehicle constraints."""

    def __init__(self, lost_timeout_seconds: float) -> None:
        self.state: SystemState = SystemState.BOOT
        self.lost_timeout_seconds = lost_timeout_seconds
        self.last_packet_time: float | None = None
        self.disconnected_since: float | None = None
        self.client_count: int = 0

    def on_client_connected(self) -> None:
        self.client_count += 1
        self.disconnected_since = None
        if self.state in (SystemState.BOOT, SystemState.LOST):
            self.state = SystemState.CONNECTING
        log.debug("Client connected; count=%d state=%s", self.client_count, self.state.value)

    def on_client_disconnected(self, total_clients: int) -> None:
        self.client_count = max(total_clients, 0)
        if self.client_count == 0:
            if self.disconnected_since is None:
                self.disconnected_since = time.time()
            log.info("All ground clients disconnected; LOST timer armed")

    def on_packet_sent(self, telemetry: dict) -> None:
        self.last_packet_time = time.time()

        if self.client_count == 0:
            return

        battery = telemetry["battery"]
        temperature = telemetry["temperature"]
        degraded = battery < 20 or temperature > 80

        prev = self.state
        if self.state in (SystemState.BOOT, SystemState.CONNECTING, SystemState.LOST):
            self.state = SystemState.DEGRADED if degraded else SystemState.NOMINAL
        elif self.state == SystemState.NOMINAL and degraded:
            self.state = SystemState.DEGRADED
        elif self.state == SystemState.DEGRADED and not degraded:
            self.state = SystemState.NOMINAL

        if self.state != prev:
            log.info("System state %s -> %s", prev.value, self.state.value)

    def check_timeout(self) -> None:
        now = time.time()
        dc = self.disconnected_since
        if dc is not None and (now - dc) > self.lost_timeout_seconds:
            if self.state != SystemState.LOST:
                log.warning(
                    "Link LOST: no ground clients within %.1f s",
                    self.lost_timeout_seconds,
                )
            self.state = SystemState.LOST
            return

        lpt = self.last_packet_time
        if lpt is not None and (now - lpt) > self.lost_timeout_seconds:
            if self.state != SystemState.LOST:
                log.warning(
                    "Link LOST: no telemetry within %.1f s",
                    self.lost_timeout_seconds,
                )
            self.state = SystemState.LOST
