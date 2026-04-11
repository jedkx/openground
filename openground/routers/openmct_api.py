"""REST helpers for Open MCT historical requests."""

from __future__ import annotations

import time

from fastapi import APIRouter, Query

from openground.core.runtime import GroundStationRuntime


def create_openmct_router(runtime: GroundStationRuntime) -> APIRouter:
    router = APIRouter(prefix="/api/openmct", tags=["openmct"])

    @router.get("/telemetry/latest")
    async def latest_telemetry() -> dict:
        return {"data": runtime.latest_packet}

    @router.get("/telemetry/history")
    async def telemetry_history(
        start: int | None = Query(default=None),
        end: int | None = Query(default=None),
    ) -> dict:
        now = int(time.time() * 1000)
        if start is None:
            start = max(0, now - (30 * 60 * 1000))
        if end is None:
            end = now

        rows = [p for p in runtime.history if start <= p.get("epoch_ms", 0) <= end]
        return {"data": rows}

    return router
