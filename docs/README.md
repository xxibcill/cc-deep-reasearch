# Documentation Guide

Use these docs as the current contributor entry points:

- [`USAGE.md`](USAGE.md): CLI commands, configuration, and operator workflows
- [`opportunity-radar-prd.md`](opportunity-radar-prd.md): detailed product requirements doc for the proposed proactive opportunity-discovery workspace
- [`PREFLIGHT.md`](PREFLIGHT.md): Low-cost preflight validation before running live research
- [`DASHBOARD_GUIDE.md`](DASHBOARD_GUIDE.md): comprehensive dashboard guide covering architecture, usage, APIs, telemetry flow, and caveats
- [`../dashboard/README.md`](../dashboard/README.md): frontend development commands, runtime env vars, and backend wiring for the Next.js dashboard
- [`RESEARCH_WORKFLOW.md`](RESEARCH_WORKFLOW.md): pipeline phases, orchestrator ownership, and package boundaries
- [`content-generation/content-generation.md`](content-generation/content-generation.md): full short-form content-generation workflow, stage contracts, CLI usage, persistence, and current caveats
- [`content-generation/content-gen-backlog.md`](content-generation/content-gen-backlog.md): persistent content backlog model, lifecycle, and storage
- [`content-generation/content-gen-artifact.md`](content-generation/content-gen-artifact.md): pipeline artifacts, persistence layers, dashboard control surface, and production boundary
- [`beats.md`](beats.md): detailed guide to beat structure, beat lifecycle, beat constraints, targeted revision, and visual handoff in the content-generation pipeline
- [`select-beat-structure-prompts.md`](select-beat-structure-prompts.md): self-contained prompt for choosing a beat structure from only a content pillar and angle statement
- [`brief-management.md`](brief-management.md): persistent brief management, lifecycle states, revision history, approval workflows, and rollout guide
- [`TELEMETRY.md`](TELEMETRY.md): persisted telemetry model and monitoring workflow
- [`REALTIME_MONITORING.md`](REALTIME_MONITORING.md): FastAPI + Next.js operator console for live monitoring
- [`RELEASING.md`](RELEASING.md): release checklist, version bump workflow, and changelog expectations

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
