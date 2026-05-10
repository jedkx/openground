from __future__ import annotations

import base64
import binascii
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from openground.adapters.http_ingest import HttpIngestAdapter
from openground.deps import verify_ingest_token
from openground.mission.registry import MissionRegistry

log = logging.getLogger(__name__)

_OCTET_STREAM = frozenset({"application/octet-stream", "application/x-ccsds-tlm"})


class TelemetryPayload(BaseModel):
    """Accepts any JSON object with numeric values — no required fields."""
    model_config = ConfigDict(extra="allow")


class CcsdsBase64Ingest(BaseModel):
    packet_base64: str = Field(..., description="Standard base64-encoded CCSDS packet.")
    source: str | None = None
    ingress_id: str | None = None


def _meta(kind: str, source: str | None, ingress_id: str | None) -> dict[str, Any]:
    m: dict[str, Any] = {"kind": kind}
    if source:
        m["source"] = source
    if ingress_id:
        m["ingress_id"] = ingress_id
    return m


async def _read_raw_packet(request: Request) -> tuple[bytes, str | None, str | None]:
    ct = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

    if ct in _OCTET_STREAM:
        raw = await request.body()
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty body")
        return raw, None, None

    if not ct or ct.startswith("application/json"):
        payload = await request.json()
        if not isinstance(payload, dict) or "packet_base64" not in payload:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail='Expected application/octet-stream or JSON {"packet_base64":"…"}',
            )
        body = CcsdsBase64Ingest.model_validate(payload)
        try:
            raw = base64.b64decode(body.packet_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64: {exc}",
            ) from exc
        return raw, body.source, body.ingress_id

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Unsupported Content-Type for /ingest/packet",
    )


def _require_ingest_adapter(registry: MissionRegistry, mission_id: str | None) -> HttpIngestAdapter:
    runtime = registry.get(mission_id) if mission_id else registry.get_default()
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id!r} not found",
        )
    if not isinstance(runtime.adapter, HttpIngestAdapter):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mission {runtime.mission_id!r} does not accept HTTP ingest "
                   f"(adapter={type(runtime.adapter).__name__})",
        )
    return runtime.adapter


def create_ingest_router(registry: MissionRegistry) -> APIRouter:
    router = APIRouter(tags=["ingest"])
    legacy = APIRouter(prefix="/api/v1/ingest")
    missions = APIRouter(prefix="/api/missions")

    @legacy.post("/telemetry", status_code=status.HTTP_202_ACCEPTED)
    async def post_telemetry_legacy(body: TelemetryPayload, request: Request) -> dict[str, str]:
        adapter = _require_ingest_adapter(registry, None)
        verify_ingest_token(adapter.token, request)
        await adapter.push_normalized(body.model_dump(), _meta("http_json", None, None))
        return {"status": "accepted", "mode": "normalized"}

    @legacy.post("/packet", status_code=status.HTTP_202_ACCEPTED)
    async def post_packet_legacy(request: Request) -> dict[str, Any]:
        adapter = _require_ingest_adapter(registry, None)
        verify_ingest_token(adapter.token, request)
        raw, source, ingress_id = await _read_raw_packet(request)
        try:
            await adapter.push_ccsds(raw, _meta("ccsds_raw", source, ingress_id))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return {"status": "accepted", "mode": "ccsds_raw", "bytes": len(raw)}

    @missions.post("/{mission_id}/ingest/telemetry", status_code=status.HTTP_202_ACCEPTED)
    async def post_telemetry(
        mission_id: str,
        body: TelemetryPayload,
        request: Request,
    ) -> dict[str, str]:
        adapter = _require_ingest_adapter(registry, mission_id)
        verify_ingest_token(adapter.token, request)
        await adapter.push_normalized(body.model_dump(), _meta("http_json", None, None))
        return {"status": "accepted", "mode": "normalized", "mission": mission_id}

    @missions.post("/{mission_id}/ingest/packet", status_code=status.HTTP_202_ACCEPTED)
    async def post_packet(mission_id: str, request: Request) -> dict[str, Any]:
        adapter = _require_ingest_adapter(registry, mission_id)
        verify_ingest_token(adapter.token, request)
        raw, source, ingress_id = await _read_raw_packet(request)
        try:
            await adapter.push_ccsds(raw, _meta("ccsds_raw", source, ingress_id))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return {"status": "accepted", "mode": "ccsds_raw", "bytes": len(raw), "mission": mission_id}

    router.include_router(legacy)
    router.include_router(missions)
    return router
