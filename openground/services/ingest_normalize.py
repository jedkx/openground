from __future__ import annotations

import time
from typing import Any


def normalize_ingest_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Pass through all user-supplied fields, adding ground timestamps if absent."""
    out = {k: v for k, v in fields.items() if v is not None}
    out.setdefault("epoch_ms", int(time.time() * 1000))
    out.setdefault("timestamp", time.strftime("%H:%M:%S", time.gmtime()))
    return out
