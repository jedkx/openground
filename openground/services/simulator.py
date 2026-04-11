"""1-D trajectory + ISA-like thermal model; parameters from :class:`SimulationProfile`."""

from __future__ import annotations

import math
import random
import time
from enum import StrEnum

from openground.simulation_profile import SimulationProfile, get_profile


class FlightPhase(StrEnum):
    LAUNCH = "LAUNCH"
    POWERED = "POWERED"
    COASTING = "COASTING"
    APOGEE = "APOGEE"
    DESCENT = "DESCENT"
    LANDED = "LANDED"


def format_met_hhmmss(met_ms: int) -> str:
    """Mission Elapsed Time as HH:MM:SS (ground MET, T0 = mission start epoch)."""
    total_s = max(0, met_ms // 1000)
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TelemetrySimulator:
    """Vertical dynamics with drag; phase machine driven by elapsed simulated time."""

    def __init__(self, profile: SimulationProfile | None = None) -> None:
        self.profile = profile or get_profile("nominal")
        self.phase = FlightPhase.LAUNCH
        self.phase_elapsed_s = 0.0
        self.altitude = 0.0
        self.velocity = 0.0
        self.temperature = 25.0
        self.battery = 100.0
        self.lat = 39.9255
        self.lon = 32.8663
        self.mission_start_epoch_ms: int = int(time.time() * 1000)

    def _air_density(self, altitude_m: float) -> float:
        return max(0.2, 1.225 * (1.0 - 0.0000226 * max(altitude_m, 0.0)))

    def _drag_force(self, velocity: float, altitude: float, parachute: bool) -> float:
        rho = self._air_density(altitude)
        p = self.profile
        if parachute:
            return 0.5 * rho * p.cd_descent * p.area_descent_m2 * velocity * velocity
        return 0.5 * rho * p.cd_powered * p.area_powered_m2 * velocity * velocity

    def _advance_phase(self, dt: float) -> None:
        self.phase_elapsed_s += dt
        p = self.profile

        if self.phase == FlightPhase.LAUNCH and self.phase_elapsed_s >= p.t_pad_hold_s:
            self.phase = FlightPhase.POWERED
            self.phase_elapsed_s = 0.0

        elif self.phase == FlightPhase.POWERED and self.phase_elapsed_s >= p.t_powered_s:
            self.phase = FlightPhase.COASTING
            self.phase_elapsed_s = 0.0

        elif self.phase == FlightPhase.COASTING and self.velocity <= 0:
            self.phase = FlightPhase.APOGEE
            self.phase_elapsed_s = 0.0

        elif self.phase == FlightPhase.APOGEE and self.phase_elapsed_s >= p.t_apogee_hold_s:
            self.phase = FlightPhase.DESCENT
            self.phase_elapsed_s = 0.0

        elif self.phase == FlightPhase.DESCENT and self.altitude <= 0:
            self.phase = FlightPhase.LANDED
            self.phase_elapsed_s = 0.0
            self.altitude = 0.0
            self.velocity = 0.0

        elif self.phase == FlightPhase.LANDED and self.phase_elapsed_s >= p.t_landed_s:
            self.phase = FlightPhase.LAUNCH
            self.phase_elapsed_s = 0.0
            self.altitude = 0.0
            self.velocity = 0.0
            self.battery = 100.0
            self.mission_start_epoch_ms = int(time.time() * 1000)

    def _integrate(self, dt: float) -> None:
        p = self.profile
        m = p.mass_kg

        if self.phase == FlightPhase.LAUNCH:
            self.velocity = 0.0
            self.altitude = 0.0

        elif self.phase == FlightPhase.POWERED:
            v = max(self.velocity, 0.0)
            drag = self._drag_force(v, self.altitude, parachute=False)
            vib = p.vibration_mps2 * math.sin(self.phase_elapsed_s * 12.566)
            acc = (p.thrust_n - drag) / m - p.g + vib
            self.velocity = max(0.0, self.velocity + acc * dt)
            self.altitude = max(0.0, self.altitude + self.velocity * dt)

        elif self.phase == FlightPhase.COASTING:
            v = max(self.velocity, 0.0)
            drag = self._drag_force(v, self.altitude, parachute=False)
            acc = -(drag / m) - p.g
            self.velocity = self.velocity + acc * dt
            self.altitude = max(0.0, self.altitude + self.velocity * dt)

        elif self.phase == FlightPhase.APOGEE:
            self.velocity = 0.0

        elif self.phase == FlightPhase.DESCENT:
            drag = self._drag_force(abs(self.velocity), self.altitude, parachute=True)
            acc = (drag / m) - p.g
            self.velocity = max(-p.v_terminal_max_mps, self.velocity + acc * dt)
            self.altitude = max(0.0, self.altitude + self.velocity * dt)

        elif self.phase == FlightPhase.LANDED:
            self.velocity = 0.0
            self.altitude = 0.0

    def step(self, dt: float) -> dict:
        if dt <= 0:
            dt = 1.0
        self._advance_phase(dt)
        self._integrate(dt)

        p = self.profile
        t_k = p.temp_sea_level_k - p.temp_lapse_k_per_m * max(self.altitude, 0.0)
        t_c = t_k - 273.15 + random.uniform(-p.temp_noise_k, p.temp_noise_k)
        self.temperature = max(-60.0, t_c)

        # Pad / landed: no discharge (simplified umbilical + recovery).
        if self.phase not in (FlightPhase.LAUNCH, FlightPhase.LANDED):
            drain = random.uniform(p.battery_drain_per_s_min, p.battery_drain_per_s_max) * dt
            self.battery = max(0.0, self.battery - drain)
        j = p.gps_jitter_deg
        self.lat += random.uniform(-j, j)
        self.lon += random.uniform(-j, j)

        now_ms = int(time.time() * 1000)
        met_ms = max(0, now_ms - self.mission_start_epoch_ms)

        return {
            "altitude": round(self.altitude, 2),
            "velocity": round(abs(self.velocity), 2),
            "temperature": round(self.temperature, 2),
            "battery": round(self.battery, 2),
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "phase": self.phase.value,
            "epoch_ms": now_ms,
            "timestamp": time.strftime("%H:%M:%S"),
            "mission_start_epoch_ms": self.mission_start_epoch_ms,
            "met_ms": met_ms,
            "met_hhmmss": format_met_hhmmss(met_ms),
        }
