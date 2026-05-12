"""EnrichmentStep contract — implement this to add processing stages to the pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from openground.sdk.frame import TelemetryFrame


class EnrichmentContext:
    """Mutable container passed through each EnrichmentStep.

    Steps read from ``frame`` and write their results into ``envelope``.
    The final envelope becomes the broadcast/storage payload.
    """

    __slots__ = ("frame", "envelope")

    def __init__(self, frame: TelemetryFrame) -> None:
        self.frame: TelemetryFrame = frame
        self.envelope: dict[str, Any] = {}


class EnrichmentStep(ABC):
    """Single processing stage in the enrichment pipeline.

    Implement ``apply`` to read from ``ctx.frame`` and mutate ``ctx.envelope``.
    Steps are applied in the order they appear in the ``Enricher`` step list.

    Override the lifecycle hooks if your step needs to react to client or
    timeout events (e.g. a state-machine step).  Default implementations
    are no-ops so most steps don't need to care.
    """

    @abstractmethod
    async def apply(self, ctx: EnrichmentContext) -> None: ...

    def on_client_connected(self) -> None:
        pass

    def on_client_disconnected(self, total_clients: int) -> None:
        pass

    def check_timeout(self) -> None:
        pass
