"""Vendor-neutral HTTP ingress for external telemetry (lab links, brokers, other ground writers)."""

from __future__ import annotations

import base64
import binascii
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from openground.config import Settings
from openground.core.runtime import GroundStationRuntime
from openground.deps import build_ingest_token_checker

log = logging.getLogger(__name__)

_OCTET_STREAM = frozenset({"application/octet-stream", "application/x-ccsds-tlm"})


class NormalizedTelemetryIngest(BaseModel):
    """Scalars that :func:`openground.ccsds.build_packet` expects, plus optional MET / routing labels."""

    model_config = ConfigDict(extra="allow")

    altitude: float
    velocity: float
    temperature: float
    battery: float
    lat: float
    lon: float
    phase: str | None = None
    epoch_ms: int | None = None
    mission_start_epoch_ms: int | None = None
    source: str | None = Field(
        default=None,
        description="Opaque producer label (ground routing, not vehicle identity).",
    )
    ingress_id: str | None = Field(
        default=None,
        description="Optional trace id from upstream systems.",
    )


class CcsdsBase64Ingest(BaseModel):
    """When a binary body is awkward (e.g. some proxies), send the same octets as standard base64."""

    packet_base64: str = Field(..., description="Standard base64.")
    source: str | None = None
    ingress_id: str | None = None


def _labels_for_ingest(
    *,
    kind: str,
    source: str | None,
    ingress_id: str | None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {"kind": kind}
    if source:
        meta["source"] = source
    if ingress_id:
        meta["ingress_id"] = ingress_id
    return meta


async def _read_raw_packet(request: Request) -> tuple[bytes, str | None, str | None]:
    """Return raw frame bytes and optional routing labels from Content-Type-specific bodies."""
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
                detail='Expected Content-Type: application/octet-stream or JSON '
                '{"packet_base64":"..."}',
            )
        body = CcsdsBase64Ingest.model_validate(payload)
        try:
            raw = base64.b64decode(body.packet_base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64: {e}",
            ) from e
        return raw, body.source, body.ingress_id

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Unsupported Content-Type for /ingest/packet",
    )


def create_ingest_router(runtime: GroundStationRuntime, settings: Settings) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/ingest",
        tags=["ingest"],
        dependencies=[Depends(build_ingest_token_checker(settings))],
    )

    @router.post(
        "/telemetry",
        status_code=status.HTTP_202_ACCEPTED,
        summary="Ingest normalized scalars (framed as CCSDS inside OpenGround).",
    )
    async def post_telemetry(
        body: NormalizedTelemetryIngest,
    ) -> dict[str, str]:
        fields = body.model_dump(exclude_none=False)
        meta = _labels_for_ingest(
            kind="http_json_normalized",
            source=body.source,
            ingress_id=body.ingress_id,
        )
        await runtime.ingest_normalized_json(fields, meta)
        log.debug("Ingest normalized telemetry (source=%s)", body.source)
        return {"status": "accepted", "mode": "normalized"}

    @router.post(
        "/packet",
        status_code=status.HTTP_202_ACCEPTED,
        summary="Ingest a raw CCSDS-like packet (octet-stream or JSON with base64).",
    )
    async def post_packet(
        request: Request,
    ) -> dict[str, Any]:
        raw, source, ingress_id = await _read_raw_packet(request)
        meta = _labels_for_ingest(kind="ccsds_raw", source=source, ingress_id=ingress_id)
        try:
            await runtime.ingest_ccsds_raw(raw, meta)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

        log.debug("Ingest raw packet (%d bytes)", len(raw))
        return {"status": "accepted", "mode": "ccsds_raw", "bytes": len(raw)}

    return router
