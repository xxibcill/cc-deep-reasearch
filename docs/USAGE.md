# Inqulume Studio Usage

The browser dashboard is the supported operator surface. The legacy Click CLI,
`python -m cc_deep_research`, and the Streamlit telemetry dashboard are no
longer part of the project.

## Install

```bash
uv sync --locked
cd dashboard
npm ci
npx playwright install chromium
cd ..
```

Use Python 3.11 or 3.12 and Node.js 24 (22 minimum).

## Start

Development stack:

```bash
./scripts/dashboard-dev
```

Production-style local stack:

```bash
./scripts/dashboard-start
```

The preferred ports are:

- dashboard: `http://localhost:3000`
- API: `http://localhost:8000/api`
- WebSocket base: `ws://localhost:8000/ws`

The launchers select the next available port when either preferred port is
already in use. Set `BACKEND_PORT` and `FRONTEND_PORT` to choose starting
ports explicitly.

## Configure Providers

Open **Settings** in the dashboard to edit persistent configuration and inspect
runtime environment overrides. The default config path is:

```text
~/.config/inqulume-studio/config.yaml
```

Credential environment variables include:

```bash
export TAVILY_API_KEYS="..."
export ANTHROPIC_API_KEY="..."
export OPENROUTER_API_KEY="..."
export CEREBRAS_API_KEY="..."
export MOONSHOT_API_KEY="..."  # Direct Kimi API
```

Use the health endpoint to verify the active environment:

```bash
curl -fsS http://localhost:8000/api/health
```

### Connect Kimi directly

Create a key in the [Kimi API Platform](https://platform.kimi.ai), then either
save it in **Settings → Secrets** or set `MOONSHOT_API_KEY`. The aliases
`KIMI_API_KEY`, `MOONSHOT_API_KEYS`, and `KIMI_API_KEYS` are also supported.

In **Settings → Model routing**, enable the direct Kimi provider, keep
`kimi-k3` or choose another model available to your account, then select
`kimi` for the desired agent routes. The built-in endpoint is
`https://api.moonshot.ai/v1`; no OpenRouter credential is required.

### Connect Codex through ChatGPT

Codex uses the pinned local app-server runtime rather than API-key billing.
Open **Settings**, enable the Codex provider, choose browser or device-code
sign-in, and complete the ChatGPT flow. Leave the model empty to use the
signed-in account's default model, then select `codex` for the desired routing
roles.

Credentials remain in the local Codex credential store and are never written
to the Inqulume configuration. Provider turns use isolated, ephemeral threads
with read-only sandboxing, deny-all approvals, disabled tools, and a fail-closed
check of the effective Codex and MCP configuration.

## Research Workflow

1. Open **Research**.
2. Select a launch preset or expand the plan controls.
3. Enter the research question and start the run.
4. Follow live progress in **Monitor**.
5. Review the saved session, report, artifacts, annotations, and triage state.
6. Compare the run with another session or a promoted benchmark baseline.

The HTTP entrypoint for integrations is:

```text
POST /api/research-runs
```

Run status and cancellation use:

```text
GET  /api/research-runs/{run_id}
POST /api/research-runs/{run_id}/stop
```

Stopping a run is the pause operation: the service keeps the latest verified
workflow snapshot. For a failed, cancelled, or otherwise interrupted session,
open **Artifacts** and choose **Resume research**, or call:

```text
POST /api/sessions/{session_id}/resume
Idempotency-Key: <unique-client-key>
```

Resume creates a new run and session; it never rewrites the original. Staged
runs reuse completed strategy, query-expansion, and source-collection work.
Planner runs reuse completed task groups. A checkpoint is offered for resume
only when its version, checksum, configuration fingerprint, and phase
prerequisites validate successfully.

## Session Operations

The dashboard supports listing, searching, sorting, archiving, restoring,
bulk deletion, telemetry browsing, report viewing, trace export, annotations,
triage, checkpoints, and resume flows.

Useful read-only API checks:

```bash
curl -fsS 'http://localhost:8000/api/sessions?limit=20'
curl -fsS http://localhost:8000/api/sessions/<session-id>
curl -fsS http://localhost:8000/api/sessions/<session-id>/events
curl -fsS http://localhost:8000/api/sessions/<session-id>/debug-export
```

## Content Generation

Use **Content** for:

- strategy readiness and operating fitness
- backlog creation, triage, selection, and execution briefs
- managed briefs and revision history
- pipeline launch, live stage progress, stop, and resume
- script review and variants
- QC approval and issue tracking
- publish readiness, reusable assets, audit history, and maintenance proposals

The API is grouped under `/api/content-gen`. See
[content-generation.md](content-generation.md) for lifecycle and ownership
details.

## Radar, Benchmarks, and Knowledge

- **Radar** manages sources, scans, opportunities, feedback, and handoff to the
  content backlog.
- **Benchmark** runs the corpus, compares results, manages promoted baselines,
  and evaluates release gates.
- **Knowledge** exposes the evidence graph, health, cleanup, and long-running
  maintenance jobs.

These workflows are dashboard/API features; there are no separate command-line
entrypoints.

## Operations API

Read-only examples:

```bash
curl -fsS http://localhost:8000/api/operations/service/status
curl -fsS http://localhost:8000/api/operations/service/conflicts
curl -fsS http://localhost:8000/api/operations/secrets/inventory
curl -fsS http://localhost:8000/api/operations/data-paths
curl -fsS http://localhost:8000/api/operations/backup/plan
curl -fsS http://localhost:8000/api/operations/upgrade/report
curl -fsS http://localhost:8000/api/operations/runbooks
```

Mutation endpoints such as backup creation, retention enforcement, cache
clearing, session deletion, and service stop should only be called after
reviewing the corresponding dry-run or status response.

## Data Locations

Project state is stored under `~/.config/inqulume-studio/`, including:

```text
config.yaml
sessions/
telemetry/
knowledge/
content-gen/
radar/
```

Do not edit active telemetry or DuckDB files while the backend is running.

## Backend-Only Development

```bash
uv run uvicorn cc_deep_research.web_server:create_app \
  --factory \
  --ws websockets-sansio \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
```

Then start only Next.js:

```bash
cd dashboard
npm run dev:frontend
```

## Validation

Run the canonical offline check from the repository root:

```bash
./scripts/preflight
```

See [PREFLIGHT.md](PREFLIGHT.md) for the exact commands and expected coverage.
