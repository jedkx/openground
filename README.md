# OpenGround

Learning sandbox: **Open MCT** (object tree, telemetry providers, live + history) and **CCSDS-style** primary headers + a fixed six-float payload (`openground/ccsds.py`). A tiny FastAPI loop produces sample telemetry, frames it, enriches JSON for the UI, and streams over WebSocket. Not mission software and not a full CCSDS implementation—just enough to see how the pieces fit.

```bash
uv sync --group dev
npm install
uv run uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. Use **Flight deck** / **Telemetry Channels**; use Open MCT’s Create menu for overlay/stacked plots on channels.

Modes (`OPENGROUND_TELEMETRY_MODE`): default **`sim`** with `OPENGROUND_SCENARIO` (`nominal`, `sport`, `gentle`, `stress`); **`milestone_replay`** from `data/demo_documented_milestones.json` (or `OPENGROUND_MILESTONE_TIMELINE_PATH`); **`iss_public`** uses the public Where The ISS At? API (network; some fields placeholders). Legacy `artemis_timeline` → `milestone_replay`.

API: WebSocket `/ws` (JSON frames); `GET /api/openmct/telemetry/latest`, `GET /api/openmct/telemetry/history?start=&end=` (epoch ms). Env: `openground/config.py`, `.env.example`.

```bash
make verify   # ruff + pytest; `/openmct` mount skipped if `node_modules/openmct/dist` missing
```

Run `npm install` (or `npm ci`) first so Open MCT’s `dist` exists for tests that touch the UI bundle.

MIT — see `LICENSE`.