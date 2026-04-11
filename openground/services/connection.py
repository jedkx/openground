"""WebSocket fan-out to ground displays (isolated failures per client)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._active_clients: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_clients.append(websocket)
        log.debug("WebSocket accepted; active=%d", len(self._active_clients))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active_clients:
            self._active_clients.remove(websocket)
            log.debug("WebSocket removed; active=%d", len(self._active_clients))

    async def broadcast(self, message: dict) -> None:
        if not self._active_clients:
            return

        results = await asyncio.gather(
            *[client.send_json(message) for client in self._active_clients],
            return_exceptions=True,
        )

        disconnected: list[WebSocket] = []
        for client, result in zip(self._active_clients, results, strict=True):
            if isinstance(result, Exception):
                log.warning("Broadcast failed for client: %s", result)
                disconnected.append(client)

        for client in disconnected:
            self.disconnect(client)

    @property
    def client_count(self) -> int:
        return len(self._active_clients)
