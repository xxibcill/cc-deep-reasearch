# P8-T3 - Add Knowledge CLI And Linting

## Functional Feature Outcome

Operators can initialize, ingest, backfill, rebuild, export, inspect, and lint the local knowledge graph from the CLI.

## Why This Task Exists

The knowledge graph should be operable before it becomes part of planning. A CLI gives a safe way to build confidence, backfill older sessions, inspect output, and repair data quality problems without changing the dashboard or research runtime first.

## Scope

- Add `cc-deep-research knowledge` commands:
  - `init`
  - `ingest-session <session_id>`
  - `backfill`
  - `rebuild-index`
  - `export-graph`
  - `inspect <id-or-path>`
  - `lint`
- Add lint checks for:
  - broken wikilinks
  - orphan pages
  - graph nodes without backing pages or raw evidence
  - unsupported claims
  - stale pages for time-sensitive topics
  - contradictory claims
  - missing source traces
  - missing index entries
- Add JSON and Markdown output modes where useful.
- Add exit codes suitable for CI gating.

## Implementation Notes

- Keep lint deterministic first. LLM-assisted contradiction review can be a later enhancement.
- Use graph rebuild to verify SQLite can be recreated from raw/wiki files.
- Export graph as stable JSON for dashboard and tests.
- Make `backfill` resumable and safe to re-run.
- Include dry-run output for commands that write files.

## Test Plan

- CLI tests for command registration and option parsing.
- Init/backfill/rebuild/export tests using temporary vault directories.
- Lint fixture tests for each lint category.
- Exit-code tests for clean, warning, and error lint results.
- Snapshot tests for exported graph JSON shape.

## Acceptance Criteria

- Operators can create and maintain the knowledge vault entirely from the CLI.
- Backfill can ingest existing saved sessions without live credentials.
- Lint findings are actionable and include file paths, node IDs, or source IDs.
- Rebuilding the graph from files produces stable graph output.
- CLI commands are documented in usage docs.

## Verification Commands

```bash
uv run pytest tests/test_session_store.py tests/test_web_server_session_routes.py -x
uv run ruff check src/cc_deep_research/cli src/cc_deep_research/knowledge tests/
```

## Risks

- Lint can become noisy. Separate blocking errors from advisory warnings.
- Backfill over many sessions can be slow. Make progress visible and keep writes idempotent.
