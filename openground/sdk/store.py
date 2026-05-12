"""TelemetryStore contract — implement this to plug in a custom storage backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class TelemetryStore(ABC):
    """Pluggable storage backend for telemetry envelopes.

    The default implementation is ``PostgresTelemetryStore``.
    A lightweight ``MemoryTelemetryStore`` is available for dev/test.
    """

    @abstractmethod
    async def insert_from_enriched(self, envelope: dict[str, Any]) -> None:
        """Persist a single enriched envelope."""
        ...

    @abstractmethod
    async def query_range(
        self,
        start_ms: int,
        end_ms: int,
        *,
        mission_id: str,
        limit: int = 50_000,
    ) -> list[dict[str, Any]]:
        """Return envelopes whose epoch_ms falls within [start_ms, end_ms]."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by this store."""
        ...

    @classmethod
    @abstractmethod
    async def connect(cls, dsn: str, **kwargs: Any) -> "TelemetryStore":
        """Create and return a connected store instance."""
        ...
