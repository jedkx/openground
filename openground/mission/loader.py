"""Factory: build a :class:`~openground.mission.runtime.MissionRuntime` from config."""

from __future__ import annotations

import logging
from typing import Any

from openground.adapters.http_ingest import HttpIngestAdapter
from openground.mission.config import MissionConfig
from openground.mission.runtime import MissionRuntime
from openground.pipeline.pipeline import FanoutPipeline
from openground.pipeline.workers import BroadcastWorker, StorageWorker

log = logging.getLogger(__name__)


def build_mission_runtime(
    config: MissionConfig,
    store: Any = None,
) -> MissionRuntime:
    """Construct a fully-wired :class:`MissionRuntime` ready to be started."""
    adapter = HttpIngestAdapter(mission_id=config.id, config=config.adapter)

    broadcast_worker = BroadcastWorker()
    pipeline = FanoutPipeline()
    pipeline.add_worker(broadcast_worker)

    if store is not None:
        pipeline.add_worker(StorageWorker(store))
        log.debug("Mission %r: Postgres storage worker attached", config.id)

    return MissionRuntime(
        config=config,
        adapter=adapter,
        pipeline=pipeline,
        broadcast_worker=broadcast_worker,
        store=store,
    )
