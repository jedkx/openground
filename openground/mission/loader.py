"""Factory: build a :class:`~openground.mission.runtime.MissionRuntime` from config."""

from __future__ import annotations

import logging

from openground.adapters.http_ingest import HttpIngestAdapter
from openground.mission.config import AdapterConfig, HttpIngestAdapterConfig, MissionConfig
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
from openground.sdk.adapter import TelemetryAdapter
from openground.sdk.store import TelemetryStore
from openground.services.sequence import SequenceMonitor
from openground.services.state_machine import StateMachine

log = logging.getLogger(__name__)


def _build_adapter(mission_id: str, config: AdapterConfig, queue_maxsize: int) -> TelemetryAdapter:
    """Instantiate the correct TelemetryAdapter for the given config type.

    To add a new adapter: create its config dataclass, add it to AdapterConfig
    union in mission/config.py, and add a branch here.
    """
    if isinstance(config, HttpIngestAdapterConfig):
        return HttpIngestAdapter(
            mission_id=mission_id,
            config=config,
            ingest_queue_maxsize=queue_maxsize,
        )
    raise TypeError(f"No adapter implementation for config type {type(config).__name__!r}")


def build_mission_runtime(
    config: MissionConfig,
    store: TelemetryStore | None = None,
) -> MissionRuntime:
    """Construct a fully-wired :class:`MissionRuntime` ready to be started."""
    adapter = _build_adapter(config.id, config.adapter, config.pipeline.ingest_queue_maxsize)

    specs = {c.id: c for c in config.channels}
    severities = {c.id: c.severity for c in config.channels}
    state_step = StateStep(StateMachine(config.lost_timeout_seconds))
    enricher = Enricher(
        steps=[
            MetadataStep(mission_id=config.id, source_id=adapter.source_id),
            SequenceStep(SequenceMonitor()),
            state_step,
            CcsdsStep(),
            LimitViolationStep(specs, severities=severities),
        ]
    )

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
