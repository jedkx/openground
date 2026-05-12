"""ASGI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from openground.config import Settings, load_settings
from openground.logging_config import configure_logging
from openground.mission.config import HttpIngestAdapterConfig, MissionConfig, load_missions_file
from openground.mission.loader import build_mission_runtime
from openground.mission.registry import MissionRegistry
from openground.routers.envelope_adapter import create_envelope_adapter_router
from openground.routers.health import create_health_router
from openground.routers.ingest import create_ingest_router
from openground.routers.openmct_api import create_openmct_router
from openground.routers.websocket import register_websocket
from openground.sdk.store import TelemetryStore
from openground.store.telemetry_postgres import PostgresTelemetryStore

log = logging.getLogger(__name__)


def _default_mission_from_settings(s: Settings) -> MissionConfig:
    """Build a single MissionConfig from env-var settings (no missions.toml fallback)."""
    return MissionConfig(
        id="default",
        name="Default Mission",
        adapter=HttpIngestAdapterConfig(token=s.ingest_token),
        history_maxlen=s.history_maxlen,
        lost_timeout_seconds=s.lost_timeout_seconds,
        database_url=s.database_url,
    )


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings.log_level)

    mission_configs = load_missions_file(settings.missions_file)
    if not mission_configs:
        log.info(
            "No missions.toml found at %r — using env-var defaults",
            settings.missions_file,
        )
        mission_configs = [_default_mission_from_settings(settings)]

    global_db_url = settings.database_url
    registry = MissionRegistry()
    _stores: dict[str, TelemetryStore] = {}

    async def _get_or_create_store(dsn: str, mc: MissionConfig) -> TelemetryStore:
        if dsn not in _stores:
            _stores[dsn] = await PostgresTelemetryStore.connect(
                dsn, storage_config=mc.storage
            )
        return _stores[dsn]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        for mc in mission_configs:
            dsn = mc.database_url or global_db_url
            store = await _get_or_create_store(dsn, mc) if dsn else None
            runtime = build_mission_runtime(mc, store=store)
            registry.register(runtime)

        await registry.start_all()
        yield
        await registry.stop_all()

        for store in _stores.values():
            await store.close()

    app = FastAPI(
        title="OpenGround",
        description="Multi-mission ground station telemetry service.",
        version="0.1.0",
        lifespan=lifespan,
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
            "Open MCT dist missing (%s); run npm install. /openmct will 404.",
            openmct_path.resolve(),
        )

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(static_path / "index.html")

    app.include_router(create_health_router(registry))
    app.include_router(create_openmct_router(registry))
    app.include_router(create_ingest_router(registry))
    app.include_router(create_envelope_adapter_router(registry))
    register_websocket(app, registry)

    return app


app = create_app()
