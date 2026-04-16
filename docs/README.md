# Documentation Guide

Use these docs as the current contributor entry points:

- [`USAGE.md`](USAGE.md): CLI commands, configuration, and operator workflows
- [`PREFLIGHT.md`](PREFLIGHT.md): Low-cost preflight validation before running live research
- [`DASHBOARD_GUIDE.md`](DASHBOARD_GUIDE.md): comprehensive dashboard guide covering architecture, usage, APIs, telemetry flow, and caveats
- [`../dashboard/README.md`](../dashboard/README.md): frontend development commands, runtime env vars, and backend wiring for the Next.js dashboard
- [`RESEARCH_WORKFLOW.md`](RESEARCH_WORKFLOW.md): pipeline phases, orchestrator ownership, and package boundaries
- [`content-generation.md`](content-generation.md): full short-form content-generation workflow, stage contracts, CLI usage, persistence, and current caveats
- [`brief-management.md`](brief-management.md): persistent brief management, lifecycle states, revision history, approval workflows, and rollout guide
- [`TELEMETRY.md`](TELEMETRY.md): persisted telemetry model and monitoring workflow
- [`REALTIME_MONITORING.md`](REALTIME_MONITORING.md): FastAPI + Next.js operator console for live monitoring
- [`IMPROVEMENT_PLAN.md`](IMPROVEMENT_PLAN.md): capability assessment and roadmap for making traces answer operator questions faster

Current code layout:

- CLI bootstrap and command registration: [`src/cc_deep_research/cli/main.py`](../src/cc_deep_research/cli/main.py)
- CLI subcommands: [`src/cc_deep_research/cli/`](../src/cc_deep_research/cli)
- config package: [`src/cc_deep_research/config/`](../src/cc_deep_research/config)
- models package: [`src/cc_deep_research/models/`](../src/cc_deep_research/models)
- orchestration internals: [`src/cc_deep_research/orchestration/`](../src/cc_deep_research/orchestration)
- telemetry live readers: [`src/cc_deep_research/telemetry/live.py`](../src/cc_deep_research/telemetry/live.py)
- telemetry DuckDB analytics: [`src/cc_deep_research/telemetry/ingest.py`](../src/cc_deep_research/telemetry/ingest.py) and [`src/cc_deep_research/telemetry/query.py`](../src/cc_deep_research/telemetry/query.py)
- telemetry compatibility exports: [`src/cc_deep_research/telemetry/__init__.py`](../src/cc_deep_research/telemetry/__init__.py)
- real-time monitoring backend: [`src/cc_deep_research/web_server.py`](../src/cc_deep_research/web_server.py) and [`src/cc_deep_research/event_router.py`](../src/cc_deep_research/event_router.py)
- Next.js dashboard frontend: [`dashboard/src/`](../dashboard/src)
- stable root API: [`src/cc_deep_research/__init__.py`](../src/cc_deep_research/__init__.py)
