"""Adapter endpoints for generic event envelopes.

Converts external wrapper payloads into OpenGround's ingest pipeline.
Supports the legacy ``/api/v1/adapters/envelope`` (default mission) and the
new ``/api/missions/{id}/adapters/envelope`` (per-mission).
"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from openground.adapters.envelope_mapper import (
    envelope_identifiers,
    envelope_meta,
    envelope_to_ingest_mode,
)
from openground.adapters.http_ingest import HttpIngestAdapter
from openground.deps import verify_ingest_token
from openground.mission.registry import MissionRegistry


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    external_event_id: str | None = None
    relay_event_id: str | None = None  # backward-compat alias
    event_type: str
    payload: dict[str, Any]


def create_envelope_adapter_router(registry: MissionRegistry) -> APIRouter:
    router = APIRouter(tags=["adapters"])

    async def _dispatch(
        adapter: HttpIngestAdapter,
        body: EventEnvelope,
        request: Request,
    ) -> dict[str, str]:
        verify_ingest_token(adapter.token, request)

        external_id, event_type = envelope_identifiers(body.model_dump())
        payload = body.payload or {}
        source_hint = payload.get("source") if isinstance(payload.get("source"), str) else None
        meta = envelope_meta(external_id, event_type, source_hint)

        mode = envelope_to_ingest_mode(payload)
        if mode == "normalized":
            await adapter.push_normalized(payload, meta)
            return {"status": "accepted", "mode": "normalized", "adapter": "envelope"}

        packet_b64 = payload.get("packet_base64")
        if not isinstance(packet_b64, str) or not packet_b64.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="payload.packet_base64 must be a non-empty string",
            )
        try:
            raw = base64.b64decode(packet_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid packet_base64: {exc}",
            ) from exc
        await adapter.push_ccsds(raw, meta)
        return {"status": "accepted", "mode": "ccsds_raw", "adapter": "envelope"}

    def _get_adapter(mission_id: str | None) -> HttpIngestAdapter:
        runtime = registry.get(mission_id) if mission_id else registry.get_default()
        if runtime is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id!r} not found",
            )
        if not isinstance(runtime.adapter, HttpIngestAdapter):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mission {runtime.mission_id!r} does not accept HTTP ingest",
            )
        return runtime.adapter

    # Legacy route
    @router.post("/api/v1/adapters/envelope", status_code=status.HTTP_202_ACCEPTED)
    async def post_envelope_legacy(body: EventEnvelope, request: Request) -> dict[str, str]:
        return await _dispatch(_get_adapter(None), body, request)

    # Per-mission route
    @router.post(
        "/api/missions/{mission_id}/adapters/envelope",
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def post_envelope(
        mission_id: str,
        body: EventEnvelope,
        request: Request,
    ) -> dict[str, str]:
        return await _dispatch(_get_adapter(mission_id), body, request)

    return router
