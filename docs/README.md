# Documentation Guide

Use these docs as the current contributor entry points:

- [`USAGE.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md): CLI commands, configuration, and operator workflows
- [`RESEARCH_WORKFLOW.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW.md): pipeline phases, orchestrator ownership, and package boundaries
- [`TELEMETRY.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/TELEMETRY.md): persisted telemetry model and monitoring workflow
- [`refactor/README.md`](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/README.md): refactor landing state and migration notes

Current code layout:

- CLI commands: [`src/cc_deep_research/cli/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli)
- config package: [`src/cc_deep_research/config/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config)
- models package: [`src/cc_deep_research/models/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models)
- telemetry live readers: [`src/cc_deep_research/telemetry/live.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/live.py)
- telemetry DuckDB analytics: [`src/cc_deep_research/telemetry/ingest.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/ingest.py) and [`src/cc_deep_research/telemetry/query.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/query.py)
- stable root API: [`src/cc_deep_research/__init__.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/__init__.py)
