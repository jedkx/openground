from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from openground.sdk.channel import ChannelSpec
from openground.sdk.frame import TelemetryFrame


class TelemetryAdapter(ABC):
    """Contract for all telemetry sources — built-in and third-party.

    Implement source_id, declared_channels, and stream.
    start/stop are called by MissionRuntime on lifecycle transitions
    and are the right place to acquire/release I/O resources.
    """

    @property
    @abstractmethod
    def source_id(self) -> str: ...

    @abstractmethod
    def declared_channels(self) -> list[ChannelSpec]: ...

    @abstractmethod
    def stream(self) -> AsyncIterator[TelemetryFrame]: ...

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass
