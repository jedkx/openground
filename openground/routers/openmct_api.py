from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from openground.mission.registry import MissionRegistry
from openground.mission.runtime import MissionRuntime  # noqa: TC001


def create_openmct_router(registry: MissionRegistry) -> APIRouter:
    router = APIRouter(tags=["openmct"])

    def _to_ms(value: float | int | None, *, default: int) -> int:
        return default if value is None else int(value)

    def _numeric_keys(envelope: dict) -> list[str]:
        excluded = {"epoch_ms"}
        return sorted(
            k for k, v in envelope.items()
            if k not in excluded and isinstance(v, (int, float)) and not isinstance(v, bool)
        )

    async def _history(
        runtime: MissionRuntime,
        start: float | int | None,
        end: float | int | None,
    ) -> dict[str, Any]:
        now = int(time.time() * 1000)
        start_ms = _to_ms(start, default=max(0, now - 30 * 60 * 1000))
        end_ms = _to_ms(end, default=now)
        if runtime.store is not None:
            data = await runtime.store.query_range(start_ms, end_ms, mission_id=runtime.mission_id)
            return {"data": data}
        return {"data": runtime.history_envelopes(start_ms, end_ms)}

    def _get_or_404(mission_id: str) -> MissionRuntime:
        runtime = registry.get(mission_id)
        if runtime is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id!r} not found",
            )
        return runtime

    # Metadata: declared channel specs (unit, min, max, description)
    @router.get("/api/openmct/telemetry/metadata")
    async def telemetry_metadata() -> dict:
        runtime = registry.get_default()
        if runtime is None:
            return {"channels": []}
        return {
            "channels": [
                {
                    "id": c.id,
                    "unit": c.unit,
                    "min": c.min_val,
                    "max": c.max_val,
                    "description": c.description,
                }
                for c in runtime.adapter.declared_channels()
            ]
        }

    @router.get("/api/missions/{mission_id}/telemetry/metadata")
    async def mission_metadata(mission_id: str) -> dict:
        runtime = _get_or_404(mission_id)
        return {
            "mission_id": mission_id,
            "channels": [
                {
                    "id": c.id,
                    "unit": c.unit,
                    "min": c.min_val,
                    "max": c.max_val,
                    "description": c.description,
                }
                for c in runtime.adapter.declared_channels()
            ],
        }

    # Legacy routes — keep existing frontend working
    @router.get("/api/openmct/telemetry/latest")
    async def latest_telemetry() -> dict:
        runtime = registry.get_default()
        return {"data": runtime.latest_envelope if runtime else None}

    @router.get("/api/openmct/telemetry/schema")
    async def telemetry_schema() -> dict:
        runtime = registry.get_default()
        if runtime is None or runtime.latest_envelope is None:
            return {"channels": []}
        return {"channels": _numeric_keys(runtime.latest_envelope)}

    @router.get("/api/openmct/telemetry/history")
    async def telemetry_history(
        start: float | int | None = Query(default=None),
        end: float | int | None = Query(default=None),
    ) -> dict:
        runtime = registry.get_default()
        if runtime is None:
            return {"data": []}
        return await _history(runtime, start, end)

    # Per-mission routes
    @router.get("/api/missions/{mission_id}/telemetry/latest")
    async def mission_latest(mission_id: str) -> dict:
        return {"data": _get_or_404(mission_id).latest_envelope}

    @router.get("/api/missions/{mission_id}/telemetry/schema")
    async def mission_schema(mission_id: str) -> dict:
        runtime = _get_or_404(mission_id)
        declared = [c.id for c in runtime.adapter.declared_channels()]
        if runtime.latest_envelope is None:
            return {"channels": [], "declared": declared}
        return {"channels": _numeric_keys(runtime.latest_envelope), "declared": declared}

    @router.get("/api/missions/{mission_id}/telemetry/history")
    async def mission_history(
        mission_id: str,
        start: float | int | None = Query(default=None),
        end: float | int | None = Query(default=None),
    ) -> dict:
        return await _history(_get_or_404(mission_id), start, end)

    return router
