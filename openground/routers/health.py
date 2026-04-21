"""Liveness and minimal operational metadata for monitors."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from openground.core.runtime import GroundStationRuntime


def create_health_router(runtime: GroundStationRuntime) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/v1/status")
    async def ops_status() -> dict[str, Any]:
        """Ground-side snapshot (not flight vehicle truth)."""
        lp = runtime.latest_packet
        return {
            "service": "openground",
            "websocket_clients": runtime.connections.client_count,
            "system_state": runtime.state.state.value,
            "last_epoch_ms": lp.get("epoch_ms") if lp else None,
            "sequence_count": runtime.sequence_count,
            "server_time_ms": int(time.time() * 1000),
            "telemetry_archive": "postgres"
            if runtime.telemetry_store is not None
            else "memory",
        }

    return router
