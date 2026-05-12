from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from openground.sdk.frame import EnrichedFrame
from openground.sdk.store import TelemetryStore
from openground.services.connection import ConnectionManager

log = logging.getLogger(__name__)


class PipelineWorker(ABC):
    @abstractmethod
    async def handle(self, frame: EnrichedFrame) -> None: ...

    async def on_error(self, exc: Exception, frame: EnrichedFrame) -> None:
        """Called when handle() raises. Default: log and drop."""
        log.exception(
            "Worker %s error (mission=%s seq=%d)",
            type(self).__name__,
            frame.frame.mission_id,
            frame.frame.seq,
        )

    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class BroadcastWorker(PipelineWorker):
    def __init__(self) -> None:
        self.connections = ConnectionManager()

    async def handle(self, frame: EnrichedFrame) -> None:
        await self.connections.broadcast(frame.envelope)


class StorageWorker(PipelineWorker):
    def __init__(self, store: TelemetryStore) -> None:
        self._store = store

    async def handle(self, frame: EnrichedFrame) -> None:
        await self._store.insert_from_enriched(frame.envelope)
