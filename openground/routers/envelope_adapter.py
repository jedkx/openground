"""Adapter endpoints for generic event envelopes.

Converts external wrapper payloads into OpenGround's vendor-neutral ingest API.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from openground.adapters.envelope_mapper import (
    envelope_identifiers,
    envelope_meta,
    envelope_to_ingest_mode,
)
from openground.config import Settings
from openground.core.runtime import GroundStationRuntime
from openground.deps import build_ingest_token_checker


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    external_event_id: str | None = None
    relay_event_id: str | None = None  # compatibility alias for Relay wrapper
    event_type: str
    payload: dict[str, Any]


def create_envelope_adapter_router(runtime: GroundStationRuntime, settings: Settings) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/adapters",
        tags=["adapters"],
        dependencies=[Depends(build_ingest_token_checker(settings))],
    )

    async def _ingest_from_envelope(body: EventEnvelope) -> dict[str, str]:
        external_id, event_type = envelope_identifiers(body.model_dump())
        payload = body.payload or {}
        source_hint = payload.get("source") if isinstance(payload.get("source"), str) else None
        meta = envelope_meta(external_id, event_type, source_hint)

        mode = envelope_to_ingest_mode(payload)
        if mode == "normalized":
            await runtime.ingest_normalized_json(payload, meta)
            return {"status": "accepted", "mode": "normalized", "adapter": "envelope"}

        packet_b64 = payload.get("packet_base64")
        if not isinstance(packet_b64, str) or not packet_b64.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="payload.packet_base64 must be a non-empty string",
            )
        try:
            raw = base64.b64decode(packet_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid packet_base64: {e}") from e
        await runtime.ingest_ccsds_raw(raw, meta)
        return {"status": "accepted", "mode": "ccsds_raw", "adapter": "envelope"}

    @router.post(
        "/envelope",
        status_code=status.HTTP_202_ACCEPTED,
        summary="Accept generic event envelope and forward to core ingest.",
    )
    async def post_envelope(body: EventEnvelope) -> dict[str, str]:
        return await _ingest_from_envelope(body)

    return router
