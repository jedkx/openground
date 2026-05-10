from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any

from openground.ccsds import parse_packet
from openground.sdk.channel import ChannelSpec
from openground.sdk.frame import EnrichedFrame, TelemetryFrame
from openground.services.sequence import SequenceMonitor
from openground.services.state_machine import StateMachine

log = logging.getLogger(__name__)


class Enricher:
    def __init__(
        self,
        mission_id: str,
        lost_timeout_seconds: float = 5.0,
        channel_specs: Mapping[str, ChannelSpec] | None = None,
    ) -> None:
        self._mission_id = mission_id
        self._sequence = SequenceMonitor()
        self._state = StateMachine(lost_timeout_seconds)
        self._specs = channel_specs or {}

    def on_client_connected(self) -> None:
        self._state.on_client_connected()

    def on_client_disconnected(self, total_clients: int) -> None:
        self._state.on_client_disconnected(total_clients)

    def check_timeout(self) -> None:
        self._state.check_timeout()

    def process(self, frame: TelemetryFrame) -> EnrichedFrame:
        seq_stats = self._sequence.observe(frame.seq)
        self._state.on_packet_received()

        envelope: dict[str, Any] = dict(frame.channels)

        if frame.labels:
            envelope.update(frame.labels)

        envelope["mission_id"] = frame.mission_id
        envelope["source_id"] = frame.source_id
        envelope["epoch_ms"] = frame.epoch_ms
        envelope["seq"] = frame.seq
        envelope.setdefault(
            "timestamp",
            time.strftime("%H:%M:%S", time.gmtime(frame.epoch_ms / 1000)),
        )

        envelope.update(frame.display_meta)
        envelope["source"] = dict(frame.source_meta)
        envelope["system_state"] = self._state.state.value

        ccsds: dict[str, Any] = {
            "seq": frame.seq,
            "lost": seq_stats["lost"],
            "loss_rate": seq_stats["loss_rate"],
        }
        if frame.raw_bytes is not None:
            ccsds["size"] = len(frame.raw_bytes)
            try:
                ccsds["apid"] = parse_packet(frame.raw_bytes)["header"]["apid"]
            except Exception:
                pass
        envelope["ccsds"] = ccsds

        violations = self._check_limits(frame.channels)
        if violations:
            envelope["limit_violations"] = violations

        return EnrichedFrame(frame=frame, envelope=envelope)

    def _check_limits(self, channels: Mapping[str, float]) -> list[dict[str, Any]]:
        violations = []
        for name, value in channels.items():
            spec = self._specs.get(name)
            if spec is None:
                continue
            if spec.min_val is not None and value < spec.min_val:
                violations.append({"channel": name, "value": value, "min": spec.min_val})
            if spec.max_val is not None and value > spec.max_val:
                violations.append({"channel": name, "value": value, "max": spec.max_val})
        return violations
