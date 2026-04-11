"""ASGI application factory and shared runtime."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from openground.config import load_settings
from openground.core.runtime import GroundStationRuntime
from openground.logging_config import configure_logging
from openground.routers.health import create_health_router
from openground.routers.openmct_api import create_openmct_router
from openground.routers.websocket import register_websocket

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings.log_level)
    runtime = GroundStationRuntime(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await runtime.start()
        yield
        await runtime.stop()

    app = FastAPI(
        title="OpenGround",
        description="Ground station telemetry service (WebSocket + Open MCT adapters).",
        lifespan=lifespan,
        version="0.1.0",
    )

    static_path = Path(settings.static_dir)
    if not static_path.is_dir():
        log.warning("Static directory missing: %s", static_path.resolve())

    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    openmct_path = Path(settings.openmct_dist_dir)
    if openmct_path.is_dir():
        app.mount("/openmct", StaticFiles(directory=settings.openmct_dist_dir), name="openmct")
    else:
        log.warning(
            "Open MCT dist missing (%s); run npm install. /openmct will 404 until then.",
            openmct_path.resolve(),
        )

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_path / "index.html")

    app.include_router(create_health_router(runtime))
    app.include_router(create_openmct_router(runtime))
    register_websocket(app, runtime)

    return app


app = create_app()
