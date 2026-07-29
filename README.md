# Inqulume Studio

Inqulume Studio is a local deep-research platform with a Next.js operator
console and FastAPI backend. It supports staged research, live telemetry,
session review, benchmark runs, opportunity radar, and a content-generation
pipeline.

Current codebase version: `0.1.0`

## Supported Runtime

The browser dashboard is the product entrypoint. The former Click CLI and
Streamlit telemetry UI have been retired.

- Python 3.11 or 3.12
- Node.js 24 recommended (22 minimum)
- `uv` for Python environments and locking
- npm for the dashboard lockfile

## Quick Start

```bash
uv sync --locked
cd dashboard
npm ci
cd ..
./scripts/dashboard-dev
```

The launcher starts:

- FastAPI at `http://localhost:8000`
- Next.js at `http://localhost:3000`

Open the dashboard, configure provider credentials under **Settings**, then
start a run from **Research**.

For a production-style local build:

```bash
./scripts/dashboard-start
```

## Backend Only

```bash
uv run uvicorn cc_deep_research.web_server:create_app \
  --factory \
  --ws websockets-sansio \
  --host 127.0.0.1 \
  --port 8000
```

The API is available under `http://localhost:8000/api`.

## Configuration

Persistent configuration lives at:

```text
~/.config/inqulume-studio/config.yaml
```

The Settings dashboard reads and updates the supported configuration schema.
Environment variables can override provider credentials and runtime settings,
including:

- `TAVILY_API_KEYS`
- `ANTHROPIC_API_KEY`
- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `CC_DEEP_RESEARCH_CONFIG`

## Development

Run the complete offline validation surface:

```bash
./scripts/preflight
```

That command verifies the Python lock, lint, types, all Python tests, dashboard
lint and unit tests, a production build, smoke journeys, and the accessibility
baseline.

## Architecture

```text
dashboard/                         Next.js operator console
src/cc_deep_research/web_server.py FastAPI application factory
src/cc_deep_research/research_runs Research-run application service
src/cc_deep_research/orchestration Staged research workflow
src/cc_deep_research/content_gen   Content-generation API and pipeline
src/cc_deep_research/radar         Opportunity-radar API and services
src/cc_deep_research/telemetry     Live and historical telemetry
```

## Documentation

- [Usage and operations](docs/USAGE.md)
- [Dashboard guide](docs/DASHBOARD_GUIDE.md)
- [Research workflow](docs/RESEARCH_WORKFLOW.md)
- [Content generation](docs/content-generation.md)
- [Telemetry architecture](docs/TELEMETRY.md)
- [Dependency maintenance](docs/DEPENDENCY_MAINTENANCE.md)
- [Preflight](docs/PREFLIGHT.md)

## Repository

[github.com/xxibcill/cc-deep-reasearch](https://github.com/xxibcill/cc-deep-reasearch)

## License

MIT
