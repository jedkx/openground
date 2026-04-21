"""Append-only telemetry archive for history queries beyond in-memory deque."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger(__name__)


class TelemetryStore:
    """Postgres-backed storage for finalized telemetry frames."""

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
        schema_sql = (Path(__file__).resolve().parent / "schema_telemetry.sql").read_text(encoding="utf-8")
        async with pool.connection() as conn:
            await conn.execute(schema_sql)
        log.info("Postgres telemetry store ready (table=openground_telemetry)")
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()
        log.info("Postgres telemetry store closed")

    @staticmethod
    def _columns_from_enriched(enriched: dict[str, Any]) -> tuple[Any, ...]:
        ccsds = enriched.get("ccsds")
        if not isinstance(ccsds, dict):
            ccsds = {}
        sim = enriched.get("sim")
        if not isinstance(sim, dict):
            sim = {}
        apid = ccsds.get("apid")
        seq = ccsds.get("seq")
        size = ccsds.get("size")
        src = sim.get("source")
        return (
            int(enriched.get("epoch_ms", 0)),
            int(apid) if apid is not None else None,
            int(seq) if seq is not None else 0,
            int(size) if size is not None else 0,
            str(sim.get("telemetry_mode", "unknown"))[:128],
            str(src)[:512] if src is not None else None,
            Jsonb(enriched),
        )

    async def insert_from_enriched(self, enriched: dict[str, Any]) -> None:
        """Persist one finalized frame; column extraction is best-effort from the envelope."""
        row = self._columns_from_enriched(enriched)
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO openground_telemetry (
                    event_time_ms,
                    apid,
                    sequence_count,
                    frame_octet_length,
                    telemetry_mode,
                    ingress_source,
                    envelope
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                row,
            )

    async def query_range(
        self,
        start_ms: int,
        end_ms: int,
        *,
        limit: int = 50_000,
    ) -> list[dict[str, Any]]:
        """Return enriched packets ordered by event time (ascending)."""
        cap = max(1, min(limit, 200_000))
        async with self._pool.connection() as conn:
            res = await conn.execute(
                """
                SELECT envelope
                FROM openground_telemetry
                WHERE event_time_ms >= %s AND event_time_ms <= %s
                ORDER BY event_time_ms ASC
                LIMIT %s
                """,
                (start_ms, end_ms, cap),
            )
            rows = await res.fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            env = row["envelope"]
            if isinstance(env, dict):
                out.append(env)
        return out
