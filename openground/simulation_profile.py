"""Named simulation profiles — tweak vehicle & environment without code edits.

Pick with ``OPENGROUND_SCENARIO=<name>`` (see README).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SimulationProfile:
    """One coherent vehicle + timeline + sensor noise set."""

    name: str
    thrust_n: float
    mass_kg: float
    g: float
    # Timeline (seconds of simulated time at current dt integration)
    t_pad_hold_s: float
    t_powered_s: float
    t_apogee_hold_s: float
    t_landed_s: float
    # Aerodynamics (1-D equivalent)
    cd_powered: float
    area_powered_m2: float
    cd_descent: float
    area_descent_m2: float
    v_terminal_max_mps: float
    # Environment / sensors
    temp_sea_level_k: float
    temp_lapse_k_per_m: float
    temp_noise_k: float
    battery_drain_per_s_min: float
    battery_drain_per_s_max: float
    gps_jitter_deg: float
    # Small forcing on powered acceleration (visual “vibration” on plots)
    vibration_mps2: float


PRESETS: dict[str, SimulationProfile] = {
    "nominal": SimulationProfile(
        name="nominal",
        thrust_n=1500.0,
        mass_kg=50.0,
        g=9.81,
        t_pad_hold_s=3.0,
        t_powered_s=15.0,
        t_apogee_hold_s=2.0,
        t_landed_s=10.0,
        cd_powered=0.75,
        area_powered_m2=0.03,
        cd_descent=1.3,
        area_descent_m2=0.6,
        v_terminal_max_mps=20.0,
        temp_sea_level_k=288.15,
        temp_lapse_k_per_m=0.0065,
        temp_noise_k=0.6,
        battery_drain_per_s_min=0.04,
        battery_drain_per_s_max=0.10,
        gps_jitter_deg=0.00005,
        vibration_mps2=0.35,
    ),
    "sport": SimulationProfile(
        name="sport",
        thrust_n=2200.0,
        mass_kg=42.0,
        g=9.81,
        t_pad_hold_s=2.0,
        t_powered_s=12.0,
        t_apogee_hold_s=2.0,
        t_landed_s=8.0,
        cd_powered=0.72,
        area_powered_m2=0.028,
        cd_descent=1.25,
        area_descent_m2=0.62,
        v_terminal_max_mps=22.0,
        temp_sea_level_k=288.15,
        temp_lapse_k_per_m=0.0065,
        temp_noise_k=0.9,
        battery_drain_per_s_min=0.06,
        battery_drain_per_s_max=0.14,
        gps_jitter_deg=0.00008,
        vibration_mps2=0.55,
    ),
    "gentle": SimulationProfile(
        name="gentle",
        thrust_n=1200.0,
        mass_kg=55.0,
        g=9.81,
        t_pad_hold_s=4.0,
        t_powered_s=18.0,
        t_apogee_hold_s=3.0,
        t_landed_s=12.0,
        cd_powered=0.78,
        area_powered_m2=0.032,
        cd_descent=1.35,
        area_descent_m2=0.58,
        v_terminal_max_mps=18.0,
        temp_sea_level_k=288.15,
        temp_lapse_k_per_m=0.0065,
        temp_noise_k=0.25,
        battery_drain_per_s_min=0.02,
        battery_drain_per_s_max=0.05,
        gps_jitter_deg=0.00002,
        vibration_mps2=0.1,
    ),
    "stress": SimulationProfile(
        name="stress",
        thrust_n=1600.0,
        mass_kg=48.0,
        g=9.81,
        t_pad_hold_s=2.5,
        t_powered_s=14.0,
        t_apogee_hold_s=1.5,
        t_landed_s=6.0,
        cd_powered=0.74,
        area_powered_m2=0.031,
        cd_descent=1.28,
        area_descent_m2=0.59,
        v_terminal_max_mps=21.0,
        temp_sea_level_k=293.15,
        temp_lapse_k_per_m=0.0065,
        temp_noise_k=2.5,
        battery_drain_per_s_min=0.08,
        battery_drain_per_s_max=0.20,
        gps_jitter_deg=0.00015,
        vibration_mps2=1.1,
    ),
}


def get_profile(scenario: str) -> SimulationProfile:
    key = (scenario or "nominal").strip().lower()
    p = PRESETS.get(key)
    if p is None:
        log.warning("Unknown OPENGROUND_SCENARIO=%r; using nominal", scenario)
        return PRESETS["nominal"]
    return p
