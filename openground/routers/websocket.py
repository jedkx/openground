from __future__ import annotations

import logging

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from openground.mission.registry import MissionRegistry

log = logging.getLogger(__name__)


def register_websocket(app: FastAPI, registry: MissionRegistry) -> None:
    @app.websocket("/ws")
    async def ws_telemetry(
        websocket: WebSocket,
        mission: str | None = Query(default=None),
    ) -> None:
        runtime = registry.get(mission) if mission else registry.get_default()
        if runtime is None:
            await websocket.close(code=1008, reason="Mission not found")
            return

        await runtime.connections.connect(websocket)
        runtime.on_client_connected()
        try:
            while True:
                # Drain incoming frames (pings, close handshakes) — server is push-only
                await websocket.receive_text()
        except (WebSocketDisconnect, Exception):
            log.debug("WebSocket disconnected (mission=%s)", runtime.mission_id)
        finally:
            runtime.connections.disconnect(websocket)
            runtime.on_client_disconnected(runtime.connections.client_count)
