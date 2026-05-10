"""Liveness and operational metadata endpoints."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, status

from openground.mission.registry import MissionRegistry


def create_health_router(registry: MissionRegistry) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/v1/status")
    async def ops_status() -> dict[str, Any]:
        """Ground-side snapshot for the default mission (backward-compatible)."""
        runtime = registry.get_default()
        if runtime is None:
            return {"service": "openground", "missions": 0}
        latest = runtime.latest_envelope or {}
        return {
            "service": "openground",
            "mission_id": runtime.mission_id,
            "websocket_clients": runtime.connections.client_count,
            "system_state": latest.get("system_state", "BOOT"),
            "last_epoch_ms": latest.get("epoch_ms"),
            "seq": latest.get("seq", -1),
            "server_time_ms": int(time.time() * 1000),
            "telemetry_archive": "postgres" if runtime.config.database_url else "memory",
        }

    @router.get("/api/v1/missions")
    async def list_missions() -> dict[str, Any]:
        """List all active missions with their current state."""
        missions = []
        for runtime in registry.all():
            latest = runtime.latest_envelope or {}
            sim = latest.get("source") or {}
            missions.append(
                {
                    "id": runtime.mission_id,
                    "name": runtime.config.name,
                    "adapter": type(runtime.adapter).__name__,
                    "ingest_mode": sim.get("ingest_mode", "unknown"),
                    "websocket_clients": runtime.connections.client_count,
                    "system_state": latest.get("system_state", "BOOT"),
                    "last_epoch_ms": latest.get("epoch_ms"),
                }
            )
        return {"missions": missions, "count": len(missions)}

    @router.get("/api/v1/missions/{mission_id}/status")
    async def mission_status(mission_id: str) -> dict[str, Any]:
        runtime = registry.get(mission_id)
        if runtime is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id!r} not found",
            )
        latest = runtime.latest_envelope or {}
        sim = latest.get("source") or {}
        return {
            "mission_id": runtime.mission_id,
            "name": runtime.config.name,
            "adapter": type(runtime.adapter).__name__,
            "ingest_mode": sim.get("ingest_mode", "unknown"),
            "websocket_clients": runtime.connections.client_count,
            "system_state": latest.get("system_state", "BOOT"),
            "last_epoch_ms": latest.get("epoch_ms"),
            "server_time_ms": int(time.time() * 1000),
            "telemetry_archive": "postgres" if runtime.config.database_url else "memory",
        }

    return router
