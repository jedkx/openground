"""REST helpers for Open MCT historical requests."""

from __future__ import annotations

import time
from collections.abc import Iterable

from fastapi import APIRouter, Query

from openground.core.runtime import GroundStationRuntime


def create_openmct_router(runtime: GroundStationRuntime) -> APIRouter:
    router = APIRouter(prefix="/api/openmct", tags=["openmct"])

    def _to_epoch_ms(value: float | int | None, *, default: int) -> int:
        if value is None:
            return default
        return int(value)

    def _numeric_keys(packet: dict) -> list[str]:
        excluded = {"epoch_ms", "mission_start_epoch_ms", "met_ms"}
        return sorted(
            key
            for key, value in packet.items()
            if key not in excluded and isinstance(value, (int, float)) and not isinstance(value, bool)
        )

    def _latest_packet_for_schema() -> dict | None:
        if runtime.latest_packet is not None:
            return runtime.latest_packet
        if isinstance(runtime.history, Iterable) and len(runtime.history) > 0:
            return runtime.history[-1]
        return None

    @router.get("/telemetry/latest")
    async def latest_telemetry() -> dict:
        return {"data": runtime.latest_packet}

    @router.get("/telemetry/schema")
    async def telemetry_schema() -> dict:
        packet = _latest_packet_for_schema()
        if packet is None:
            return {"channels": []}
        return {"channels": _numeric_keys(packet)}

    @router.get("/telemetry/history")
    async def telemetry_history(
        start: float | int | None = Query(default=None),
        end: float | int | None = Query(default=None),
    ) -> dict:
        now = int(time.time() * 1000)
        start_ms = _to_epoch_ms(start, default=max(0, now - (30 * 60 * 1000)))
        end_ms = _to_epoch_ms(end, default=now)

        store = runtime.telemetry_store
        if store is not None:
            data = await store.query_range(start_ms, end_ms)
            return {"data": data}

        rows = [p for p in runtime.history if start_ms <= p.get("epoch_ms", 0) <= end_ms]
        return {"data": rows}

    return router
