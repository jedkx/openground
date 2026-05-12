"""MemoryTelemetryStore — in-memory TelemetryStore for development and testing."""

from __future__ import annotations

from typing import Any

from openground.sdk.store import TelemetryStore


class MemoryTelemetryStore(TelemetryStore):
    """Stores envelopes in a plain list; no persistence across restarts.

    Use this store when no DATABASE_URL is configured and you still want
    query_range() to work (e.g. integration tests or local dev without Postgres).
    """

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    @classmethod
    async def connect(cls, dsn: str, **kwargs: Any) -> MemoryTelemetryStore:
        return cls()

    async def insert_from_enriched(self, envelope: dict[str, Any]) -> None:
        self._rows.append(envelope)

    async def query_range(
        self,
        start_ms: int,
        end_ms: int,
        *,
        mission_id: str | None = None,
        limit: int = 50_000,
    ) -> list[dict[str, Any]]:
        results = [
            r for r in self._rows
            if (mission_id is None or r.get("mission_id") == mission_id)
            and start_ms <= r.get("epoch_ms", 0) <= end_ms
        ]
        return results[:limit]

    async def close(self) -> None:
        self._rows.clear()
