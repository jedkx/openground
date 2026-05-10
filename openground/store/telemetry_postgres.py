"""Append-only telemetry archive for history queries beyond the in-memory deque."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger(__name__)


class TelemetryStore:
    """Postgres-backed storage for finalized telemetry frames.

    All missions share a single table; ``mission_id`` is used to scope queries.
    The schema is applied idempotently on :meth:`connect` so the table (and any
    new columns) are always present before the first insert.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> TelemetryStore:
        pool = AsyncConnectionPool(
            conninfo=dsn,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        await pool.open()
        schema_sql = (
            Path(__file__).resolve().parent / "schema_telemetry.sql"
        ).read_text(encoding="utf-8")
        async with pool.connection() as conn:
            await conn.execute(schema_sql)
        log.info("Postgres telemetry store ready (table=openground_telemetry)")
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()
        log.info("Postgres telemetry store closed")

    @staticmethod
    def _columns_from_enriched(enriched: dict[str, Any]) -> tuple[Any, ...]:
        ccsds = enriched.get("ccsds") or {}
        source = enriched.get("source") or {}
        apid = ccsds.get("apid")
        seq = ccsds.get("seq")
        size = ccsds.get("size")
        ingress_src = source.get("source")
        mission_id = enriched.get("mission_id")
        return (
            int(enriched.get("epoch_ms", 0)),
            str(mission_id)[:128] if mission_id is not None else None,
            int(apid) if apid is not None else None,
            int(seq) if seq is not None else 0,
            int(size) if size is not None else 0,
            str(source.get("ingest_mode", "unknown"))[:128],
            str(ingress_src)[:512] if ingress_src is not None else None,
            Jsonb(enriched),
        )

    async def insert_from_enriched(self, enriched: dict[str, Any]) -> None:
        row = self._columns_from_enriched(enriched)
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO openground_telemetry (
                    event_time_ms,
                    mission_id,
                    apid,
                    sequence_count,
                    frame_octet_length,
                    telemetry_mode,
                    ingress_source,
                    envelope
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                row,
            )

    async def query_range(
        self,
        start_ms: int,
        end_ms: int,
        *,
        mission_id: str | None = None,
        limit: int = 50_000,
    ) -> list[dict[str, Any]]:
        """Return enriched envelopes in ascending event-time order.

        When ``mission_id`` is provided the query is scoped to that mission.
        """
        cap = max(1, min(limit, 200_000))
        if mission_id is not None:
            sql = """
                SELECT envelope
                FROM openground_telemetry
                WHERE event_time_ms >= %s
                  AND event_time_ms <= %s
                  AND mission_id = %s
                ORDER BY event_time_ms ASC
                LIMIT %s
            """
            params: tuple[Any, ...] = (start_ms, end_ms, mission_id, cap)
        else:
            sql = """
                SELECT envelope
                FROM openground_telemetry
                WHERE event_time_ms >= %s
                  AND event_time_ms <= %s
                ORDER BY event_time_ms ASC
                LIMIT %s
            """
            params = (start_ms, end_ms, cap)

        async with self._pool.connection() as conn:
            res = await conn.execute(sql, params)
            rows = await res.fetchall()

        return [row["envelope"] for row in rows if isinstance(row["envelope"], dict)]
