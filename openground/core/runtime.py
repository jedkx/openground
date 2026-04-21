"""Single-writer telemetry pipeline: simulate → frame → enrich → distribute."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from collections import deque
from typing import Any

import httpx

from openground.ccsds import build_packet, parse_packet
from openground.config import Settings
from openground.services.connection import ConnectionManager
from openground.services.fault_detector import FaultDetector
from openground.services.flight_rules import evaluate_flight_rules
from openground.services.ingest_normalize import (
    normalized_http_fields_to_telemetry,
    telemetry_from_parsed_wire_packet,
)
from openground.services.iss_telemetry import fetch_iss_state, finalize_iss_packet
from openground.services.milestone_timeline import MilestoneTimeline
from openground.services.sequence import SequenceMonitor
from openground.services.simulator import TelemetrySimulator, format_met_hhmmss
from openground.services.state_machine import StateMachine
from openground.simulation_profile import get_profile
from openground.store.telemetry_postgres import TelemetryStore

log = logging.getLogger(__name__)

_TIMELINE_FALLBACK_TEMP_C = 20.0
_TIMELINE_FALLBACK_BATTERY = 99.5
_TIMELINE_FALLBACK_LAT = 28.5721
_TIMELINE_FALLBACK_LON = -80.6480


class GroundStationRuntime:
    """Owns background telemetry production and subscriber fan-out."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mode = settings.telemetry_mode.strip().lower()
        if self._mode not in ("sim", "milestone_replay", "iss_public"):
            log.warning("Unknown OPENGROUND_TELEMETRY_MODE=%r; using sim", settings.telemetry_mode)
            self._mode = "sim"
        self.connections = ConnectionManager()
        self.state = StateMachine(lost_timeout_seconds=settings.lost_timeout_seconds)
        self.faults = FaultDetector()
        self._timeline: MilestoneTimeline | None = None
        self._timeline_met_s = 0.0

        self._iss_http: httpx.AsyncClient | None = None
        self._iss_mission_start_ms: int | None = None
        self._last_iss_core: dict[str, Any] | None = None

        scenario = settings.simulation_scenario if self._mode == "sim" else "nominal"
        self.sim = TelemetrySimulator(get_profile(scenario))
        if self._mode == "milestone_replay":
            self._timeline = MilestoneTimeline.from_path(settings.milestone_timeline_path)
        if self._mode == "iss_public":
            self._iss_http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self.sequence = SequenceMonitor()

        self.sequence_count = -1
        self.link_drop_probability = settings.link_drop_probability

        self.latest_packet: dict[str, Any] | None = None
        self.history: deque[dict[str, Any]] = deque(maxlen=settings.history_maxlen)
        self._task: asyncio.Task[None] | None = None
        self._publish_lock = asyncio.Lock()
        self.telemetry_store: TelemetryStore | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        if self._settings.database_url:
            self.telemetry_store = await TelemetryStore.connect(self._settings.database_url)
        self._task = asyncio.create_task(self._telemetry_loop(), name="openground-telemetry")
        log.info(
            "Telemetry loop started (%.2f Hz, mode=%s, scenario=%s, history=%d, link_drop=%.3f)",
            self._settings.telemetry_hz,
            self._mode,
            self.sim.profile.name,
            self._settings.history_maxlen,
            self.link_drop_probability,
        )
        if self._mode == "milestone_replay":
            assert self._timeline is not None
            log.info(
                "Milestone replay mode (cycle=%.3f s, path=%s)",
                self._timeline.cycle_duration_s,
                self._settings.milestone_timeline_path,
            )
        if self._mode == "iss_public":
            log.info("ISS public API mode (url=%s)", self._settings.iss_api_url)
        if self.telemetry_store is not None:
            log.info("Telemetry archive: Postgres (openground_telemetry)")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        if self._iss_http is not None:
            await self._iss_http.aclose()
            self._iss_http = None
        if self.telemetry_store is not None:
            await self.telemetry_store.close()
            self.telemetry_store = None
        log.info("Telemetry loop stopped")

    def _telemetry_from_timeline_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        met_ms = max(0, int(round(self._timeline_met_s * 1000)))
        pc = sample.get("phase_code")
        phase = pc if isinstance(pc, str) and pc.strip() else "MILESTONE_REPLAY"
        temp = (
            float(sample["temperature_c"])
            if sample.get("temperature_c") is not None
            else _TIMELINE_FALLBACK_TEMP_C
        )
        batt = (
            float(sample["battery_pct"])
            if sample.get("battery_pct") is not None
            else _TIMELINE_FALLBACK_BATTERY
        )
        lat = (
            float(sample["lat_deg"])
            if sample.get("lat_deg") is not None
            else _TIMELINE_FALLBACK_LAT
        )
        lon = (
            float(sample["lon_deg"])
            if sample.get("lon_deg") is not None
            else _TIMELINE_FALLBACK_LON
        )
        packet: dict[str, Any] = {
            "altitude": round(float(sample["altitude_m"]), 2),
            "velocity": round(float(sample["velocity_mps"]), 2),
            "temperature": round(temp, 2),
            "battery": round(batt, 2),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "phase": phase,
            "epoch_ms": now_ms,
            "timestamp": time.strftime("%H:%M:%S"),
            "mission_start_epoch_ms": now_ms - met_ms,
            "met_ms": met_ms,
            "met_hhmmss": format_met_hhmmss(met_ms),
            "mission_event": str(sample.get("mission_event", "")),
        }
        if "met_phase_index" in sample:
            packet["met_phase_index"] = round(float(sample["met_phase_index"]), 4)
        if "accel_proxy_mps2" in sample:
            packet["accel_proxy_mps2"] = round(float(sample["accel_proxy_mps2"]), 4)
        if "earth_range_km" in sample:
            packet["earth_range_km"] = round(float(sample["earth_range_km"]), 3)
        if "moon_range_km" in sample:
            packet["moon_range_km"] = round(float(sample["moon_range_km"]), 3)
        return packet

    def _advance_timeline_met(self, period: float, cycle_s: float) -> None:
        n = self._timeline_met_s + period
        while n >= cycle_s:
            n -= cycle_s
            self.faults.reset()
        self._timeline_met_s = n

    async def _finalize_distribution_parsed(
        self,
        telemetry: dict[str, Any],
        raw_packet: bytes,
        parsed: dict[str, Any],
        sim_block: dict[str, Any],
    ) -> None:
        hdr = parsed["header"]
        seq_stats = self.sequence.observe(int(hdr["seq_count"]))
        fault_list = self.faults.check(telemetry)
        enriched: dict[str, Any] = {
            **telemetry,
            "sim": sim_block,
            "system_state": self.state.state.value,
            "faults": fault_list,
            "has_fault": bool(fault_list),
            "ccsds": {
                "apid": int(hdr["apid"]),
                "seq": int(hdr["seq_count"]),
                "size": len(raw_packet),
                "lost": seq_stats["lost"],
                "loss_rate": seq_stats["loss_rate"],
            },
        }
        flight_violations = evaluate_flight_rules(enriched)
        enriched["flight_rules"] = flight_violations
        enriched["flight_rules_ok"] = len(flight_violations) == 0

        self.state.on_packet_sent(enriched)
        enriched["system_state"] = self.state.state.value

        self.latest_packet = enriched
        self.history.append(enriched)
        await self.connections.broadcast(enriched)
        await self._archive_envelope(enriched)

    async def _archive_envelope(self, enriched: dict[str, Any]) -> None:
        store = self.telemetry_store
        if store is None:
            return
        try:
            await store.insert_from_enriched(enriched)
        except Exception:
            log.exception("telemetry archive insert failed")

    async def ingest_normalized_json(self, fields: dict[str, Any], ingress_meta: dict[str, Any]) -> None:
        """Build a CCSDS frame from normalized scalars and feed the same path as the sim loop."""
        meta_keys = frozenset({"source", "ingress_id"})
        core = {k: v for k, v in fields.items() if k not in meta_keys}
        telemetry = normalized_http_fields_to_telemetry(core)
        sim_block: dict[str, Any] = {
            "telemetry_mode": "ingest",
            "profile": "external_normalized",
            **ingress_meta,
        }
        async with self._publish_lock:
            self.sequence_count = (self.sequence_count + 1) & 0x3FFF
            raw_packet = build_packet(telemetry, self.sequence_count)
            parsed = parse_packet(raw_packet)
            await self._finalize_distribution_parsed(telemetry, raw_packet, parsed, sim_block)

    async def ingest_ccsds_raw(self, raw: bytes, ingress_meta: dict[str, Any]) -> None:
        """Accept a wire-framed packet; sequence and APID come from headers (no local seq bump)."""
        parsed = parse_packet(raw)
        now_ms = int(time.time() * 1000)
        telemetry = telemetry_from_parsed_wire_packet(parsed, now_ms=now_ms)
        sim_block: dict[str, Any] = {
            "telemetry_mode": "ingest",
            "profile": "external_ccsds",
            **ingress_meta,
        }
        async with self._publish_lock:
            await self._finalize_distribution_parsed(telemetry, raw, parsed, sim_block)

    async def _telemetry_loop(self) -> None:
        period = self._settings.telemetry_period_s
        while True:
            self.state.check_timeout()

            if self._mode == "milestone_replay":
                if self._timeline is None:
                    raise RuntimeError("milestone replay without loaded timeline")
                tl_sample = self._timeline.sample(self._timeline_met_s)
                telemetry = self._telemetry_from_timeline_sample(tl_sample)
            elif self._mode == "iss_public":
                if self._iss_http is None:
                    raise RuntimeError("ISS mode without HTTP client")
                core = await fetch_iss_state(self._iss_http, self._settings.iss_api_url)
                if core is None:
                    if self._last_iss_core is None:
                        await asyncio.sleep(period)
                        continue
                    core = dict(self._last_iss_core)
                    core["epoch_ms"] = int(time.time() * 1000)
                else:
                    self._last_iss_core = dict(core)
                if self._iss_mission_start_ms is None:
                    self._iss_mission_start_ms = int(core["epoch_ms"])
                telemetry = finalize_iss_packet(
                    core,
                    mission_start_epoch_ms=self._iss_mission_start_ms,
                )
            else:
                telemetry = self.sim.step(period)

            sim_block: dict[str, Any]
            if self._mode == "milestone_replay":
                sim_block = {
                    "profile": "openground_doc_replay",
                    "telemetry_mode": "milestone_replay",
                    "dt_s": round(period, 4),
                    "timeline_path": self._settings.milestone_timeline_path,
                }
            elif self._mode == "iss_public":
                sim_block = {
                    "profile": "wheretheiss_at",
                    "telemetry_mode": "iss_public",
                    "dt_s": round(period, 4),
                    "iss_api_url": self._settings.iss_api_url,
                    "note": (
                        "temperature/battery are UI placeholders; position/speed from public API"
                    ),
                }
            else:
                sim_block = {
                    "profile": self.sim.profile.name,
                    "telemetry_mode": "sim",
                    "dt_s": round(period, 4),
                    "thrust_n": self.sim.profile.thrust_n,
                    "mass_kg": self.sim.profile.mass_kg,
                }

            async with self._publish_lock:
                self.sequence_count = (self.sequence_count + 1) & 0x3FFF
                raw_packet = build_packet(telemetry, self.sequence_count)

                if random.random() < self.link_drop_probability:
                    log.debug("Synthetic link drop; skipping frame seq=%d", self.sequence_count)
                else:
                    parsed = parse_packet(raw_packet)
                    await self._finalize_distribution_parsed(
                        telemetry,
                        raw_packet,
                        parsed,
                        sim_block,
                    )

            if self._mode == "milestone_replay" and self._timeline is not None:
                self._advance_timeline_met(period, self._timeline.cycle_duration_s)

            await asyncio.sleep(period)
