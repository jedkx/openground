from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from openground.ccsds import SEQ_MASK, parse_packet
from openground.mission.config import HttpIngestAdapterConfig
from openground.sdk.adapter import TelemetryAdapter
from openground.sdk.channel import ChannelSpec
from openground.sdk.frame import TelemetryFrame
from openground.services.ingest_normalize import normalize_ingest_fields

log = logging.getLogger(__name__)

_QUEUE_MAXSIZE = 500


class HttpIngestAdapter(TelemetryAdapter):
    def __init__(self, mission_id: str, config: HttpIngestAdapterConfig) -> None:
        self._mission_id = mission_id
        self._config = config
        self._queue: asyncio.Queue[TelemetryFrame] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._seq = -1

    @property
    def source_id(self) -> str:
        return "http_ingest"

    @property
    def token(self) -> str:
        return self._config.token

    def declared_channels(self) -> list[ChannelSpec]:
        return []

    async def push_normalized(self, fields: dict[str, Any], meta: dict[str, Any]) -> None:
        normalized = normalize_ingest_fields(fields)
        self._seq = (self._seq + 1) & SEQ_MASK

        channels: dict[str, float] = {}
        labels: dict[str, str] = {}
        for k, v in normalized.items():
            if isinstance(v, bool):
                labels[k] = str(v).lower()
            elif isinstance(v, (int, float)):
                channels[k] = float(v)
            elif isinstance(v, str):
                labels[k] = v

        frame = TelemetryFrame(
            mission_id=self._mission_id,
            source_id=self.source_id,
            epoch_ms=int(normalized.get("epoch_ms", time.time() * 1000)),
            seq=self._seq,
            channels=channels,
            labels=labels,
            source_meta={"ingest_mode": "normalized", **meta},
        )
        self._enqueue(frame)

    async def push_ccsds(self, raw: bytes, meta: dict[str, Any]) -> None:
        parsed = parse_packet(raw)
        frame = TelemetryFrame(
            mission_id=self._mission_id,
            source_id=self.source_id,
            epoch_ms=int(time.time() * 1000),
            seq=parsed["header"]["seq_count"],
            channels={},
            raw_bytes=raw,
            source_meta={"ingest_mode": "ccsds", **meta},
        )
        self._enqueue(frame)

    async def stream(self) -> AsyncIterator[TelemetryFrame]:
        while True:
            yield await self._queue.get()

    def _enqueue(self, frame: TelemetryFrame) -> None:
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            log.warning(
                "Ingest queue full (mission=%s) — dropping frame seq=%d",
                self._mission_id,
                frame.seq,
            )
