"""Enricher — applies a sequence of EnrichmentStep instances to each TelemetryFrame."""

from __future__ import annotations

from openground.sdk.enrichment import EnrichmentContext, EnrichmentStep
from openground.sdk.frame import EnrichedFrame, TelemetryFrame


class Enricher:
    """Transforms a raw TelemetryFrame into an EnrichedFrame by running ordered steps.

    Steps are applied in list order; each step mutates ``ctx.envelope`` in place.
    Lifecycle events (client connect/disconnect, timeout) are forwarded to every
    step — steps that don't care simply inherit the no-op defaults.
    """

    def __init__(self, steps: list[EnrichmentStep]) -> None:
        self._steps = steps

    def on_client_connected(self) -> None:
        for step in self._steps:
            step.on_client_connected()

    def on_client_disconnected(self, total_clients: int) -> None:
        for step in self._steps:
            step.on_client_disconnected(total_clients)

    def check_timeout(self) -> None:
        for step in self._steps:
            step.check_timeout()

    async def process(self, frame: TelemetryFrame) -> EnrichedFrame:
        ctx = EnrichmentContext(frame)
        ctx.envelope.update(frame.channels)
        if frame.labels:
            ctx.envelope.update(frame.labels)
        for step in self._steps:
            await step.apply(ctx)
        return EnrichedFrame(frame=frame, envelope=ctx.envelope)
