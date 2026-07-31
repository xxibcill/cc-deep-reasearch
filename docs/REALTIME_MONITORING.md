# Real-time Monitoring

The supported operator console is the Next.js dashboard backed by the FastAPI
application. Research runs start through HTTP, execute in the backend process,
persist session events, and stream updates to the browser over WebSocket.

## Start the stack

From the repository root:

```bash
uv sync --locked
cd dashboard && npm ci && cd ..
./scripts/dashboard-dev
```

The development launcher starts both services. For backend-only work:

```bash
uv run uvicorn cc_deep_research.web_server:create_app \
  --factory --host 127.0.0.1 --port 8000
```

The dashboard defaults to `http://127.0.0.1:3000` and the backend to
`http://127.0.0.1:8000`.

## Runtime flow

```mermaid
flowchart LR
    UI["Next.js dashboard"] -->|POST /api/research-runs| API["FastAPI"]
    API --> JOB["ResearchRunService background job"]
    JOB --> ORCH["Research orchestrator"]
    ORCH --> MON["ResearchMonitor"]
    MON --> STORE["Session event files"]
    MON --> ROUTER["EventRouter"]
    ROUTER -->|/ws/session/{session_id}| UI
    STORE -->|session/report APIs| API
```

`ResearchMonitor` remains the event producer. The event router is the live
transport; persisted session data remains the source of truth for refresh,
reconnect, report generation, and later analysis.

## Core API

| Purpose | Endpoint |
| --- | --- |
| Start a run | `POST /api/research-runs` |
| Poll a run | `GET /api/research-runs/{run_id}` |
| Request cancellation | `POST /api/research-runs/{run_id}/stop` |
| List sessions | `GET /api/sessions` |
| Read session events | `GET /api/sessions/{session_id}/events` |
| Read a report | `GET /api/sessions/{session_id}/report` |
| Stream a session | `WS /ws/session/{session_id}` |
| Stream a content pipeline | `WS /ws/content-gen/pipeline/{pipeline_id}` |

Example:

```bash
curl -sS http://127.0.0.1:8000/api/research-runs \
  -H 'content-type: application/json' \
  -d '{"query":"How are small teams evaluating AI coding agents?","depth":"quick","realtime_enabled":true}'
```

The response is `202 Accepted` with a `run_id`. Poll that run until its
`session_id` is available, then use the session endpoints or WebSocket.

## Operational notes

- A run executes inside the backend process, using `asyncio.to_thread` so the
  API event loop remains responsive.
- Cancellation is cooperative. A stop request is recorded immediately, but a
  provider call already in progress may need to return before execution exits.
- WebSocket loss does not discard the run. Reconnect and replay persisted
  events from the session API.
- The job registry is process-local. Persisted sessions survive backend
  restarts; in-flight job status does not.
- Provider credentials are read by the backend, never by browser code.

For frontend details see [`DASHBOARD_GUIDE.md`](DASHBOARD_GUIDE.md). For event
storage and retention see [`TELEMETRY.md`](TELEMETRY.md).
