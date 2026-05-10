from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TelemetryFrame:
    """Normalized unit flowing through the pipeline from any adapter.

    channels  — numeric measurements  {"temperature": 52.3, "ram_usage": 78.1}
    labels    — string metadata       {"status": "running", "hostname": "pi-01"}
    display_meta — fields promoted to the envelope top level
    source_meta  — adapter diagnostics nested under envelope["source"]
    raw_bytes    — CCSDS wire bytes when the adapter produces binary; None otherwise
    """

    mission_id: str
    source_id: str
    epoch_ms: int
    seq: int
    channels: Mapping[str, float]
    labels: Mapping[str, str] = field(default_factory=dict)
    raw_bytes: bytes | None = None
    display_meta: Mapping[str, Any] = field(default_factory=dict)
    source_meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EnrichedFrame:
    frame: TelemetryFrame
    envelope: dict[str, Any]
