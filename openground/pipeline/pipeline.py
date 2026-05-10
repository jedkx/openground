from __future__ import annotations

import asyncio
import logging

from openground.pipeline.workers import PipelineWorker
from openground.sdk.frame import EnrichedFrame

log = logging.getLogger(__name__)

_QUEUE_MAXSIZE = 1_000


class FanoutPipeline:
    def __init__(self) -> None:
        self._slots: list[tuple[PipelineWorker, asyncio.Queue[EnrichedFrame]]] = []
        self._drain_tasks: list[asyncio.Task[None]] = []

    def add_worker(self, worker: PipelineWorker) -> None:
        if self._drain_tasks:
            raise RuntimeError("Cannot add workers after pipeline.start()")
        self._slots.append((worker, asyncio.Queue(maxsize=_QUEUE_MAXSIZE)))

    async def start(self) -> None:
        for worker, q in self._slots:
            await worker.start()
            task = asyncio.create_task(
                self._drain(worker, q),
                name=f"pipeline-{type(worker).__name__}",
            )
            self._drain_tasks.append(task)

    async def stop(self) -> None:
        for task in self._drain_tasks:
            task.cancel()
        await asyncio.gather(*self._drain_tasks, return_exceptions=True)
        self._drain_tasks.clear()
        for worker, _ in self._slots:
            await worker.stop()

    async def publish(self, frame: EnrichedFrame) -> None:
        for worker, q in self._slots:
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                log.warning(
                    "Queue full for %s (mission=%s seq=%d) — frame dropped",
                    type(worker).__name__,
                    frame.frame.mission_id,
                    frame.frame.seq,
                )

    @staticmethod
    async def _drain(worker: PipelineWorker, q: asyncio.Queue[EnrichedFrame]) -> None:
        while True:
            frame = await q.get()
            try:
                await worker.handle(frame)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Unhandled error in %s.handle()", type(worker).__name__)
            finally:
                q.task_done()
