from __future__ import annotations

import asyncio
import logging

from openground.mission.runtime import MissionRuntime

log = logging.getLogger(__name__)


class MissionRegistry:
    def __init__(self) -> None:
        self._missions: dict[str, MissionRuntime] = {}

    def register(self, runtime: MissionRuntime) -> None:
        mid = runtime.mission_id
        if mid in self._missions:
            raise ValueError(f"Mission {mid!r} is already registered")
        self._missions[mid] = runtime
        log.debug("Mission %r registered", mid)

    def get(self, mission_id: str) -> MissionRuntime | None:
        return self._missions.get(mission_id)

    def get_default(self) -> MissionRuntime | None:
        return next(iter(self._missions.values()), None)

    def all(self) -> list[MissionRuntime]:
        return list(self._missions.values())

    @property
    def mission_ids(self) -> list[str]:
        return list(self._missions.keys())

    async def start_all(self) -> None:
        await asyncio.gather(*[m.start() for m in self._missions.values()])
        log.info("All missions started (%d)", len(self._missions))

    async def stop_all(self) -> None:
        await asyncio.gather(
            *[m.stop() for m in self._missions.values()],
            return_exceptions=True,
        )
        log.info("All missions stopped")
