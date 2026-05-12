from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    """Metadata declaration for a single telemetry channel."""

    id: str
    unit: str = ""
    dtype: Literal["float", "int"] = "float"
    min_val: float | None = None
    max_val: float | None = None
    description: str = ""
    severity: str = "warning"  # e.g. "warning", "critical"
    rules: tuple[str, ...] = ()  # e.g. ("min", "max")
