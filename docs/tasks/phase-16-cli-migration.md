# Phase 16 - CLI Migration: All Features to Dashboard

## Functional Feature Outcome

All CLI commands are either available via the dashboard or deprecated with a clear path to removal.

## Why This Phase Exists

The project is consolidating on the dashboard as the sole UI. The legacy CLI in `src/cc_deep_research/cli/main.py` must be replaced by dashboard equivalents so the CLI can be removed entirely.

## Scope

- Audit all CLI commands and identify what's missing from the dashboard/API
- Implement missing features as HTTP API endpoints and dashboard UI
- Once all features are available via dashboard, remove the CLI entry point and delete `src/cc_deep_research/cli/`

## Tasks

| Task | Summary |
| --- | --- |
| [P16-T1](phase-16/p16-t1-cli-audit.md) | Audit CLI commands vs. existing API endpoints to identify gaps |
| [P16-T2](phase-16/p16-t2-knowledge-init-api.md) | Add `/api/knowledge/init` endpoint and dashboard UI for vault initialization |
| [P16-T3](phase-16/p16-t3-knowledge-backfill-api.md) | Add `/api/knowledge/backfill` endpoint and dashboard UI for session ingestion |
| [P16-T4](phase-16/p16-t4-knowledge-rebuild-index-api.md) | Add `/api/knowledge/rebuild-index` endpoint and dashboard UI |
| [P16-T5](phase-16/p16-t5-benchmark-run-api.md) | Add `/api/benchmarks/run` endpoint to trigger benchmark runs from dashboard |
| [P16-T6](phase-16/p16-t6-benchmark-compare-api.md) | Add `/api/benchmarks/compare` endpoint for run comparison |
| [P16-T7](phase-16/p16-t7-remove-cli.md) | Remove CLI entry point from `pyproject.toml` and delete `src/cc_deep_research/cli/` |

## Dependencies

- Dashboard API infrastructure already in place (`web_server.py`, `web_server_routes/`)
- Benchmark read endpoints exist at `/api/benchmarks/*` — only triggering runs is missing

## Exit Criteria

- All CLI commands have dashboard equivalents
- `cc-deep-research` console script removed from `pyproject.toml`
- `src/cc_deep_research/cli/` directory deleted
- No import references to `cc_deep_research.cli` remain in tests or code