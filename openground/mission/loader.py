"""Factory: build a :class:`~openground.mission.runtime.MissionRuntime` from config."""

from __future__ import annotations

import logging

from openground.adapters.http_ingest import HttpIngestAdapter
from openground.mission.config import MissionConfig
from openground.mission.runtime import MissionRuntime
from openground.pipeline.enricher import Enricher
from openground.pipeline.pipeline import FanoutPipeline
from openground.pipeline.steps import (
    CcsdsStep,
    LimitViolationStep,
    MetadataStep,
    SequenceStep,
    StateStep,
)
from openground.pipeline.workers import BroadcastWorker, StorageWorker
from openground.sdk.store import TelemetryStore
from openground.services.sequence import SequenceMonitor
from openground.services.state_machine import StateMachine

log = logging.getLogger(__name__)


def build_mission_runtime(
    config: MissionConfig,
    store: TelemetryStore | None = None,
) -> MissionRuntime:
    """Construct a fully-wired :class:`MissionRuntime` ready to be started."""
    adapter = HttpIngestAdapter(
        mission_id=config.id,
        config=config.adapter,
        ingest_queue_maxsize=config.pipeline.ingest_queue_maxsize,
    )


    specs = {c.id: c for c in config.channels}
    # Collect severity and rules for each channel
    severities = {c.id: c.severity for c in config.channels if hasattr(c, 'severity')}
    # Determine which rules to use for each channel (default: min/max)
    # For now, rules are not used to filter, but can be used to customize in the future
    # (e.g. only min, only max, or custom rules)
    state_step = StateStep(StateMachine(config.lost_timeout_seconds))
    enricher = Enricher(steps=[
        MetadataStep(mission_id=config.id, source_id=adapter.source_id),
        SequenceStep(SequenceMonitor()),
        state_step,
        CcsdsStep(),
        LimitViolationStep(specs, severities=severities),
    ])

    broadcast_worker = BroadcastWorker()
    pipeline = FanoutPipeline(worker_queue_maxsize=config.pipeline.worker_queue_maxsize)
    pipeline.add_worker(broadcast_worker)

    if store is not None:
        pipeline.add_worker(StorageWorker(store))
        log.debug("Mission %r: storage worker attached (%s)", config.id, type(store).__name__)

    return MissionRuntime(
        config=config,
        adapter=adapter,
        enricher=enricher,
        pipeline=pipeline,
        broadcast_worker=broadcast_worker,
        store=store,
    )
