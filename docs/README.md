# Documentation Guide

Use these docs as the current contributor entry points:

- [`USAGE.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md): CLI commands, configuration, and operator workflows
- [`RESEARCH_WORKFLOW.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW.md): pipeline phases, orchestrator ownership, and package boundaries
- [`TELEMETRY.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/TELEMETRY.md): persisted telemetry model and monitoring workflow
- [`REALTIME_MONITORING.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/REALTIME_MONITORING.md): FastAPI + Next.js operator console for live monitoring
- [`refactor/README.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/README.md): refactor landing state and migration notes

Current code layout:

- CLI bootstrap and command registration: [`src/cc_deep_research/cli/main.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli/main.py)
- CLI subcommands: [`src/cc_deep_research/cli/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli)
- config package: [`src/cc_deep_research/config/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config)
- models package: [`src/cc_deep_research/models/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models)
- orchestration internals: [`src/cc_deep_research/orchestration/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration)
- telemetry live readers: [`src/cc_deep_research/telemetry/live.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/live.py)
- telemetry DuckDB analytics: [`src/cc_deep_research/telemetry/ingest.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/ingest.py) and [`src/cc_deep_research/telemetry/query.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/query.py)
- telemetry compatibility exports: [`src/cc_deep_research/telemetry/__init__.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/__init__.py)
- real-time monitoring backend: [`src/cc_deep_research/web_server.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/web_server.py) and [`src/cc_deep_research/event_router.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/event_router.py)
- Next.js dashboard frontend: [`dashboard/src/`](/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src)
- stable root API: [`src/cc_deep_research/__init__.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/__init__.py)

Migration note:

- new contributor docs should point at package paths such as `cli/`, `config/`, `models/`, and `telemetry/`; older single-file references in historical task docs are records of the pre-refactor layout, not current targets
