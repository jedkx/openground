"""Plausibility checks on scalar telemetry (engineering rules, not FSW redundancy)."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class FaultDetector:
    def __init__(self) -> None:
        self._prev_altitude: float | None = None

    def reset(self) -> None:
        """Clear cross-frame state (e.g. after a discontinuous timeline wrap)."""
        self._prev_altitude = None

    def check(self, packet: dict[str, Any]) -> list[str]:
        faults: list[str] = []

        altitude = float(packet["altitude"])
        velocity = float(packet["velocity"])
        temperature = float(packet["temperature"])
        battery = float(packet["battery"])

        if altitude < 0:
            faults.append("Altitude below zero")
        if battery < 0 or battery > 100:
            faults.append("Battery out of range")
        if temperature < -273.15:
            faults.append("Temperature below absolute zero")

        if self._prev_altitude is not None:
            altitude_delta = abs(altitude - self._prev_altitude)
            max_allowed = max(velocity, 0.1) + 5.0
            if altitude_delta > max_allowed:
                faults.append("Altitude change exceeds physical limit")
            if velocity < 0.5 and altitude_delta > 5:
                faults.append("Inconsistent sensor relation: near-zero velocity with altitude jump")

        self._prev_altitude = altitude
        if faults:
            log.warning("Faults detected: %s", "; ".join(faults))
        return faults
