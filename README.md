# OpenGround

A core telemetry platform. Connect any data source, receive it in real time, store it in Postgres. No auth, no dashboards, no notifications — those are your responsibility. OpenGround handles the pipeline.

## How it works

```
Your Device (Pi, sensor, anything)
        │
        │  POST /api/missions/{id}/ingest/telemetry
        │  {"temperature": 52.3, "ram_usage": 78.1, "status": "ok"}
        ▼
  HttpIngestAdapter  →  Enricher  →  FanoutPipeline
                                      ├── WebSocket clients (real time)
                                      └── Postgres (history)
```

Any JSON payload is accepted — numeric fields, string fields, any key names. Nothing is hardcoded.

## Quick start

### Prerequisites

- Python 3.12+
- `uv`

### Run

```bash
uv sync --group dev
uv run uvicorn openground.application:app --reload
```

### Docker

```bash
docker compose up --build
```

- API: `http://127.0.0.1:8000`
- Postgres: `127.0.0.1:5433` (db `openground_dev`, user/pass `openground`)

## Configuration

Create `missions.toml` in the project root:

```toml
[[missions]]
id   = "raspberry-pi"
name = "Raspberry Pi"

[missions.adapter]
type  = "http_ingest"
token = "your-secret-token"   # omit or set "" to disable auth

# Optional: declare channels to get limit violation alerts
[[missions.channels]]
id   = "temperature"
unit = "°C"
max  = 80.0

[[missions.channels]]
id   = "ram_usage"
unit = "%"
min  = 0.0
max  = 100.0
```

Without `missions.toml`, a single default mission is built from environment variables.

## Sending data

```bash
# Any fields, any names
curl -X POST http://localhost:8000/api/missions/raspberry-pi/ingest/telemetry \
  -H "Authorization: Bearer your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"temperature": 52.3, "ram_usage": 78.1, "status": "running"}'
```

From Python (e.g. on a Raspberry Pi):

```python
import httpx, psutil

httpx.post(
    "http://your-server/api/missions/raspberry-pi/ingest/telemetry",
    headers={"Authorization": "Bearer your-secret-token"},
    json={
        "temperature": get_cpu_temp(),
        "ram_usage": psutil.virtual_memory().percent,
        "cpu_load": psutil.cpu_percent(),
        "hostname": "pi-01",
    },
)
```

## What you get in the envelope

Every frame broadcasted over WebSocket and stored in Postgres:

```json
{
  "temperature": 52.3,
  "ram_usage": 78.1,
  "status": "running",
  "hostname": "pi-01",
  "mission_id": "raspberry-pi",
  "source_id": "http_ingest",
  "epoch_ms": 1715000000000,
  "timestamp": "12:34:56",
  "seq": 42,
  "system_state": "NOMINAL",
  "ccsds": {"seq": 42, "lost": 0, "loss_rate": 0.0},
  "source": {"ingest_mode": "normalized"},
  "limit_violations": [{"channel": "temperature", "value": 85.0, "max": 80.0}]
}
```

`limit_violations` only appears when a declared channel exceeds its configured bounds.

## API reference

### Missions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/missions` | List all missions |
| `GET` | `/api/v1/missions/{id}/status` | Mission status |
| `GET` | `/api/v1/status` | Default mission status (backward compat) |

### Ingest

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/missions/{id}/ingest/telemetry` | JSON payload (any fields) |
| `POST` | `/api/missions/{id}/ingest/packet` | Raw CCSDS binary or `{"packet_base64": "..."}` |
| `POST` | `/api/v1/ingest/telemetry` | Default mission (backward compat) |
| `POST` | `/api/v1/ingest/packet` | Default mission (backward compat) |

### Telemetry

| Method | Path | Description |
|--------|------|-------------|
| `WS` | `/ws?mission={id}` | Real-time stream |
| `GET` | `/api/missions/{id}/telemetry/latest` | Last envelope |
| `GET` | `/api/missions/{id}/telemetry/history?start=&end=` | History (epoch ms) |
| `GET` | `/api/missions/{id}/telemetry/schema` | Discovered channel keys |
| `GET` | `/api/openmct/telemetry/*` | Open MCT routes (default mission) |

### Envelope adapter

Wraps external event systems into the ingest pipeline:

```bash
curl -X POST http://localhost:8000/api/v1/adapters/envelope \
  -H "Content-Type: application/json" \
  -d '{
    "external_event_id": "evt-001",
    "event_type": "telemetry.normalized",
    "payload": {"temperature": 52.3, "ram_usage": 78.1}
  }'
```

`relay_event_id` accepted as a backward-compatible alias for `external_event_id`.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENGROUND_MISSIONS_FILE` | `missions.toml` | Path to mission config |
| `OPENGROUND_DATABASE_URL` | _(empty)_ | Postgres DSN; omit for in-memory only |
| `OPENGROUND_INGEST_TOKEN` | _(empty)_ | Default mission ingest token |
| `OPENGROUND_HISTORY_MAX` | `5000` | In-memory frame buffer size |
| `OPENGROUND_LOST_TIMEOUT_S` | `5.0` | Seconds before state → LOST |
| `OPENGROUND_LOG_LEVEL` | `INFO` | Logging level |
| `OPENGROUND_STATIC_DIR` | `static` | Static file directory |
| `OPENGROUND_OPENMCT_DIST` | `node_modules/openmct/dist` | Open MCT dist path |

## System states

The state machine tracks ground-side connection and data health:

| State | Meaning |
|---|---|
| `BOOT` | No clients have connected yet |
| `CONNECTING` | Client connected, waiting for first frame |
| `NOMINAL` | Data flowing normally |
| `LOST` | No data or no clients for `lost_timeout_seconds` |

## Development

```bash
uv sync --group dev
uv run pytest tests/ -v
uv run ruff check openground/
uv run ruff format --check openground/
```

## Architecture

```
openground/
├── sdk/              # Public contracts: TelemetryAdapter, TelemetryFrame, ChannelSpec
├── adapters/         # HttpIngestAdapter, envelope mapper
├── pipeline/         # Enricher, FanoutPipeline, BroadcastWorker, StorageWorker
├── mission/          # MissionConfig, MissionRuntime, MissionRegistry, loader
├── services/         # SequenceMonitor, StateMachine, ConnectionManager, ingest normalize
├── routers/          # FastAPI routers: health, ingest, websocket, openmct, envelope
├── store/            # TelemetryStore (Postgres)
└── ccsds.py          # CCSDS packet header parsing
```

### Adding a custom adapter

Implement `TelemetryAdapter` from `openground.sdk.adapter`:

```python
from openground.sdk.adapter import TelemetryAdapter
from openground.sdk.channel import ChannelSpec
from openground.sdk.frame import TelemetryFrame

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

## License

MIT — see `LICENSE`.
