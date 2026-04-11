"""Real-time JSON telemetry to ground clients (server-push)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from openground.core.runtime import GroundStationRuntime

log = logging.getLogger(__name__)


def register_websocket(app: FastAPI, runtime: GroundStationRuntime) -> None:
    @app.websocket("/ws")
    async def ws_telemetry(websocket: WebSocket) -> None:
        await runtime.connections.connect(websocket)
        runtime.state.on_client_connected()

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            log.debug("WebSocket client disconnected normally")
        finally:
            runtime.connections.disconnect(websocket)
            runtime.state.on_client_disconnected(runtime.connections.client_count)
