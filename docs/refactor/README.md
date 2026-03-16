# Refactor Landing State

This directory records the post-refactor module boundaries that contributors should target.

## Final Boundaries

- CLI bootstrap and commands are split under [`src/cc_deep_research/cli/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli)
- config schema and file IO live under [`src/cc_deep_research/config/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config)
- runtime models live under [`src/cc_deep_research/models/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/models)
- orchestration internals live under [`src/cc_deep_research/orchestration/`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration)
- live telemetry readers are isolated in [`src/cc_deep_research/telemetry/live.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/live.py)
- persisted telemetry ingestion and analytics are isolated in [`src/cc_deep_research/telemetry/ingest.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/ingest.py) and [`src/cc_deep_research/telemetry/query.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/query.py)
- dashboard runtime config lives in [`dashboard/src/lib/runtime-config.ts`](/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/lib/runtime-config.ts)
- dashboard pages delegate to typed components under [`dashboard/src/components/`](/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components)

## Migration Notes

- Prefer direct imports such as `cc_deep_research.models`, `cc_deep_research.telemetry.query`, or `cc_deep_research.cli.telemetry` for new internal code.
- The package root [`cc_deep_research`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/__init__.py) now exports only version metadata, core search/session models, `SearchProvider`, and `TeamResearchOrchestrator`.
- The telemetry package root remains a compatibility barrel for stable callers. New DuckDB work should go into `telemetry.ingest` or `telemetry.query`.
