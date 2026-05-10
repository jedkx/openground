from __future__ import annotations

import logging
import time
from enum import StrEnum

log = logging.getLogger(__name__)


class SystemState(StrEnum):
    BOOT = "BOOT"
    CONNECTING = "CONNECTING"
    NOMINAL = "NOMINAL"
    LOST = "LOST"


class StateMachine:
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
        if self.client_count == 0 and self.disconnected_since is None:
            self.disconnected_since = time.time()
            log.info("All clients disconnected; LOST timer armed")

    def on_packet_received(self) -> None:
        self.last_packet_time = time.time()
        if self.state in (SystemState.BOOT, SystemState.CONNECTING, SystemState.LOST):
            self.state = SystemState.NOMINAL
            log.info("System state -> NOMINAL")

    def check_timeout(self) -> None:
        now = time.time()

        dc = self.disconnected_since
        if dc is not None and (now - dc) > self.lost_timeout_seconds:
            if self.state != SystemState.LOST:
                log.warning("Link LOST: no clients within %.1f s", self.lost_timeout_seconds)
            self.state = SystemState.LOST
            return

        lpt = self.last_packet_time
        if lpt is not None and (now - lpt) > self.lost_timeout_seconds:
            if self.state != SystemState.LOST:
                log.warning("Link LOST: no data within %.1f s", self.lost_timeout_seconds)
            self.state = SystemState.LOST
