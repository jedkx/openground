from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

from openground.mission.config import MissionConfig
from openground.pipeline.enricher import Enricher
from openground.pipeline.pipeline import FanoutPipeline
from openground.pipeline.workers import BroadcastWorker
from openground.sdk.adapter import TelemetryAdapter
from openground.sdk.frame import EnrichedFrame
from openground.sdk.store import TelemetryStore
from openground.services.connection import ConnectionManager

log = logging.getLogger(__name__)


class MissionRuntime:
    def __init__(
        self,
        config: MissionConfig,
        adapter: TelemetryAdapter,
        enricher: Enricher,
        pipeline: FanoutPipeline,
        broadcast_worker: BroadcastWorker,
        store: TelemetryStore | None = None,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._enricher = enricher
        self._pipeline = pipeline
        self._broadcast_worker = broadcast_worker
        self._store = store
        self._latest: EnrichedFrame | None = None
        self._history: deque[EnrichedFrame] = deque(maxlen=config.history_maxlen)
        self._run_task: asyncio.Task[None] | None = None
        self._timeout_task: asyncio.Task[None] | None = None

    @property
    def mission_id(self) -> str:
        return self._config.id

    @property
    def config(self) -> MissionConfig:
        return self._config

    @property
    def adapter(self) -> TelemetryAdapter:
        return self._adapter

    @property
    def store(self) -> TelemetryStore | None:
        return self._store

    @property
    def connections(self) -> ConnectionManager:
        return self._broadcast_worker.connections

    @property
    def latest_envelope(self) -> dict[str, Any] | None:
        return self._latest.envelope if self._latest else None

    def history_envelopes(
        self,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        if start_ms is None or end_ms is None:
            return [f.envelope for f in self._history]
        return [
            f.envelope
            for f in self._history
            if start_ms <= f.envelope.get("epoch_ms", 0) <= end_ms
        ]

    def on_client_connected(self) -> None:
        self._enricher.on_client_connected()

    def on_client_disconnected(self, total_clients: int) -> None:
        self._enricher.on_client_disconnected(total_clients)

    async def start(self) -> None:
        await self._adapter.start()
        await self._pipeline.start()
        self._run_task = asyncio.create_task(self._run(), name=f"mission-run-{self._config.id}")
        self._timeout_task = asyncio.create_task(
            self._timeout_loop(), name=f"mission-timeout-{self._config.id}"
        )
        log.info("Mission %r started (adapter=%s)", self._config.id, type(self._adapter).__name__)

    async def stop(self) -> None:
        for task in (self._run_task, self._timeout_task):
            if task is not None:
                task.cancel()
        await asyncio.gather(
            *(t for t in (self._run_task, self._timeout_task) if t is not None),
            return_exceptions=True,
        )
        self._run_task = None
        self._timeout_task = None
        await self._pipeline.stop()
        await self._adapter.stop()
        log.info("Mission %r stopped", self._config.id)

    async def _run(self) -> None:
        try:
            async for frame in self._adapter.stream():
                enriched = await self._enricher.process(frame)
                self._latest = enriched
                self._history.append(enriched)
                await self._pipeline.publish(enriched)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Mission %r encountered an unrecoverable error", self._config.id)
            raise

    async def _timeout_loop(self) -> None:
        interval = self._config.pipeline.timeout_check_interval_seconds
        while True:
            self._enricher.check_timeout()
            await asyncio.sleep(interval)
