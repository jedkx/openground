from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from openground.sdk.frame import EnrichedFrame
from openground.services.connection import ConnectionManager

log = logging.getLogger(__name__)


class PipelineWorker(ABC):
    @abstractmethod
    async def handle(self, frame: EnrichedFrame) -> None: ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class BroadcastWorker(PipelineWorker):
    def __init__(self) -> None:
        self.connections = ConnectionManager()

    async def handle(self, frame: EnrichedFrame) -> None:
        await self.connections.broadcast(frame.envelope)


class StorageWorker(PipelineWorker):
    def __init__(self, store: Any) -> None:
        self._store = store

    async def handle(self, frame: EnrichedFrame) -> None:
        try:
            await self._store.insert_from_enriched(frame.envelope)
        except Exception:
            log.exception(
                "Storage insert failed (mission=%s seq=%d)",
                frame.frame.mission_id,
                frame.frame.seq,
            )
