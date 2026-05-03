# P16-T1: CLI Audit — Identify Dashboard Gaps

## Summary

Audit all CLI commands in `src/cc_deep_research/cli/main.py` and map them to existing API endpoints in `src/cc_deep_research/web_server_routes/`. Document which features need to be added to the dashboard.

## Details

### Commands to Audit

**knowledge group:**
- `knowledge init` — initialize vault
- `knowledge ingest-session` — ingest single session
- `knowledge backfill` — ingest all sessions
- `knowledge rebuild-index` — clear/rebuild graph index
- `knowledge export-graph` — export to JSON/markdown
- `knowledge inspect` — inspect node/edge/page by ID
- `knowledge lint` — lint vault for issues

**benchmark group:**
- `benchmark run` — run benchmark corpus
- `benchmark compare` — compare two runs

## Acceptance Criteria

- Table mapping every CLI command to its current API status (exists / missing)
- Missing features are clearly identified for P16-T2 through P16-T6