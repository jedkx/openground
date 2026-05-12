"""SequenceStep — tracks packet sequence numbers and computes loss statistics."""

from __future__ import annotations

from openground.sdk.enrichment import EnrichmentContext, EnrichmentStep
from openground.services.sequence import SequenceMonitor


class SequenceStep(EnrichmentStep):
    """Observes the frame sequence number and writes CCSDS loss stats into the envelope."""

    def __init__(self, monitor: SequenceMonitor | None = None) -> None:
        self._monitor = monitor or SequenceMonitor()

    async def apply(self, ctx: EnrichmentContext) -> None:
        stats = self._monitor.observe(ctx.frame.seq)
        ccsds = ctx.envelope.setdefault("ccsds", {})
        ccsds["seq"] = ctx.frame.seq
        ccsds["lost"] = stats["lost"]
        ccsds["loss_rate"] = stats["loss_rate"]
