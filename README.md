# OpenGround

## Why this exists

Most telemetry setups end up with the same problem: the data collection side and the visualization side are coupled. You pick a dashboard tool, you write to its format, and now your pipeline depends on it. Swap the dashboard, rewrite the pipeline.

OpenGround sits in between. It accepts any JSON payload over HTTP, enriches it, broadcasts it over WebSocket, and archives it in Postgres. The visualization layer — Open MCT in this case — talks to OpenGround's API like it would talk to any telemetry backend. If you want to replace Open MCT tomorrow, the ingest pipeline doesn't change.

No auth, no alerting, no built-in dashboards. Those are your responsibility. OpenGround handles the pipeline.

## Why the enrichment pipeline is step-based

The naive approach is a single `Enricher` class with methods for each concern: sequence tracking, state machine, CCSDS parsing, limit checking. That works until you need to add something. Every new concern goes into the same class, the test surface grows, and swapping one step means touching code that has nothing to do with it.

Instead, each concern is its own `EnrichmentStep`. The pipeline runs them in order; each step reads from the frame and writes into the envelope. Adding a step means implementing one method and registering it in the loader — nothing else changes. Removing a step means deleting it from the list.

The tradeoff: the loader owns the step order, so it's the one place you need to look when something processes unexpectedly.

## What it does

```
Your device / script
        │
        │  POST /api/missions/{id}/ingest/telemetry
        │  {"temperature": 52.3, "ram_usage": 78.1}
        ▼
  Enricher  (steps run in order)
  ├── MetadataStep       — mission id, timestamp
  ├── SequenceStep       — packet loss tracking
  ├── StateStep          — BOOT / NOMINAL / LOST
  ├── CcsdsStep          — CCSDS header (binary only)
  └── LimitViolationStep — min/max checks
        │
        ▼
  FanoutPipeline
  ├── BroadcastWorker  →  WebSocket (real time)
  └── StorageWorker    →  Postgres (history)
```

Open MCT connects to this as a standard telemetry backend: history queries hit `/api/missions/{id}/telemetry/history`, real-time updates come over WebSocket. From Open MCT's perspective, this is just a backend — it doesn't know or care what's sending data.

## This is reference wiring

In-memory fallback when Postgres is absent, no real auth (token is a plain string), single-node only. Replace these for production:

- `IReportStorage` → bring your own `TelemetryStore` implementation
- Token check in `deps.py` → integrate your identity layer
- Single `FanoutPipeline` → add your own `PipelineWorker` for alerting, forwarding, whatever

The extension points are `TelemetryAdapter`, `EnrichmentStep`, `TelemetryStore`, and `PipelineWorker` — all abstract base classes in `openground/sdk/`.

## Run

```bash
uv sync --group dev
uv run uvicorn openground.application:app --reload
```

With Docker (includes Postgres):

```bash
docker compose up --build
```

App: `http://localhost:8000` — Open MCT loads after `npm install`.

## Configuration

`missions.toml` in the project root:

```toml
[[missions]]
id   = "my-device"
name = "My Device"

[missions.adapter]
type  = "http_ingest"
token = "your-secret-token"

# Declare channels for units and limit alerts in Open MCT
[[missions.channels]]
id          = "temperature"
unit        = "°C"
max         = 80.0
description = "CPU temperature"

[[missions.channels]]
id   = "ram_usage"
unit = "%"
min  = 0.0
max  = 100.0

# Optional tuning — these are the defaults
[missions.pipeline]
ingest_queue_maxsize           = 500
worker_queue_maxsize           = 1000
timeout_check_interval_seconds = 1.0

[missions.storage]
pool_min_size       = 1
pool_max_size       = 8
query_default_limit = 50000
```

Without `missions.toml`, a default mission is built from environment variables.

## Sending data

```bash
curl -X POST http://localhost:8000/api/missions/my-device/ingest/telemetry \
  -H "Authorization: Bearer your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"temperature": 52.3, "ram_usage": 78.1, "status": "running"}'
```

From Python:

```python
import httpx, psutil, time

while True:
    httpx.post(
        "http://your-server/api/missions/my-device/ingest/telemetry",
        headers={"Authorization": "Bearer your-secret-token"},
        json={
            "temperature": get_cpu_temp(),
            "ram_usage":   psutil.virtual_memory().percent,
            "cpu_load":    psutil.cpu_percent(),
        },
    )
    time.sleep(1)
```

Every numeric field becomes a telemetry channel in Open MCT automatically. String fields pass through in the envelope. Channels declared in `missions.toml` get units, min/max, and description; undeclared channels still stream — they just have no metadata.

## API

### Missions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/missions` | List all active missions |
| `GET` | `/api/missions/{id}/status` | Mission health snapshot |
| `GET` | `/api/status` | Default mission snapshot |

### Ingest

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/missions/{id}/ingest/telemetry` | JSON payload — any fields |
| `POST` | `/api/missions/{id}/ingest/packet` | Raw CCSDS binary or `{"packet_base64": "..."}` |

### Telemetry

| Method | Path | Description |
|--------|------|-------------|
| `WS` | `/ws?mission={id}` | Real-time envelope stream |
| `GET` | `/api/missions/{id}/telemetry/latest` | Most recent envelope |
| `GET` | `/api/missions/{id}/telemetry/history?start=&end=` | History by epoch ms |
| `GET` | `/api/missions/{id}/telemetry/metadata` | Declared channels with unit/min/max |
| `GET` | `/api/missions/{id}/telemetry/schema` | Live channel keys |

## System states

| State | Meaning |
|---|---|
| `BOOT` | No clients have connected yet |
| `CONNECTING` | Client connected, waiting for first packet |
| `NOMINAL` | Data flowing |
| `LOST` | No data or no clients for `lost_timeout_seconds` |

## Extending

### Custom enrichment step

```python
from openground.sdk import EnrichmentStep, EnrichmentContext

class GeoStep(EnrichmentStep):
    async def apply(self, ctx: EnrichmentContext) -> None:
        lat = ctx.envelope.get("lat")
        lon = ctx.envelope.get("lon")
        if lat is not None and lon is not None:
            ctx.envelope["geo"] = f"{lat:.4f},{lon:.4f}"
```

Add it to the step list in `mission/loader.py`. That's it.

### Custom adapter

```python
from openground.sdk import TelemetryAdapter, ChannelSpec, TelemetryFrame
import asyncio, time

class MyAdapter(TelemetryAdapter):
    @property
    def source_id(self) -> str:
        return "my_sensor"

    def declared_channels(self) -> list[ChannelSpec]:
        return [ChannelSpec("temperature", unit="°C", max_val=80.0)]

    async def stream(self):
        while True:
            yield TelemetryFrame(
                mission_id=self._mission_id,
                source_id=self.source_id,
                epoch_ms=int(time.time() * 1000),
                seq=self._next_seq(),
                channels={"temperature": read_sensor()},
            )
            await asyncio.sleep(1.0)
```

### Custom storage backend

```python
from openground.sdk import TelemetryStore

class RedisStore(TelemetryStore):
    async def insert_from_enriched(self, envelope): ...
    async def query_range(self, start_ms, end_ms, *, mission_id, limit=50_000): ...
    async def close(self): ...

    @classmethod
    async def connect(cls, dsn, **kwargs): ...
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENGROUND_MISSIONS_FILE` | `missions.toml` | Path to mission config |
| `OPENGROUND_DATABASE_URL` | _(empty)_ | Postgres DSN — omit for in-memory |
| `OPENGROUND_INGEST_TOKEN` | _(empty)_ | Default mission token |
| `OPENGROUND_HISTORY_MAX` | `5000` | In-memory frame buffer size |
| `OPENGROUND_LOST_TIMEOUT_S` | `5.0` | Seconds before state goes LOST |
| `OPENGROUND_LOG_LEVEL` | `INFO` | Log level |

## Development

```bash
uv run pytest tests/ -v
uv run ruff check openground/
uv run ruff format --check openground/
```

## License

MIT
