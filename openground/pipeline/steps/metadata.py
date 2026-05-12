"""MetadataStep — injects mission identity and timing fields into the envelope."""

from __future__ import annotations

import time

from openground.sdk.enrichment import EnrichmentContext, EnrichmentStep


class MetadataStep(EnrichmentStep):
    """Adds mission_id, source_id, epoch_ms, timestamp, display_meta, and source fields."""

    def __init__(self, mission_id: str, source_id: str) -> None:
        self._mission_id = mission_id
        self._source_id = source_id

    async def apply(self, ctx: EnrichmentContext) -> None:
        frame = ctx.frame
        ctx.envelope["mission_id"] = self._mission_id
        ctx.envelope["source_id"] = self._source_id
        ctx.envelope["epoch_ms"] = frame.epoch_ms
        ctx.envelope["seq"] = frame.seq
        ctx.envelope.setdefault(
            "timestamp",
            time.strftime("%H:%M:%S", time.gmtime(frame.epoch_ms / 1000)),
        )
        ctx.envelope.update(frame.display_meta)
        ctx.envelope["source"] = dict(frame.source_meta)
