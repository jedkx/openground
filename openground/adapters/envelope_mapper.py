from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException, status


def _as_string(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is required")
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} must be a string")
    s = value.strip()
    if required and not s:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is required")
    return s or None


def envelope_to_ingest_mode(payload: dict[str, Any]) -> Literal["normalized", "packet"]:
    if "packet_base64" in payload:
        return "packet"
    return "normalized"


def envelope_identifiers(body: dict[str, Any]) -> tuple[str, str]:
    external_id = _as_string(
        body.get("external_event_id") or body.get("relay_event_id"),
        "external_event_id",
        required=True,
    )
    event_type = _as_string(body.get("event_type"), "event_type", required=True)
    assert external_id is not None and event_type is not None
    return external_id, event_type


def envelope_meta(external_id: str, event_type: str, source_hint: str | None) -> dict[str, Any]:
    meta: dict[str, Any] = {"kind": "event_envelope", "external_event_id": external_id, "external_event_type": event_type}
    if source_hint:
        meta["source"] = source_hint
    return meta
