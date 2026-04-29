# P8-T2 - Ingest Research Sessions

## Functional Feature Outcome

Completed research sessions can be converted into immutable raw snapshots, source-backed Markdown wiki pages, and queryable graph records.

## Why This Task Exists

The first practical value of the knowledge graph is turning existing saved research into reusable memory without changing the hot research path. Ingest should run after session/report persistence and should also support backfilling older sessions. It must preserve the existing `ResearchSession` contract and avoid making report generation dependent on knowledge graph success.

## Scope

- Add an ingest service that accepts a `ResearchSession` plus optional cached markdown report.
- Snapshot raw artifacts into `knowledge/raw/`:
  - session JSON
  - markdown report
  - source metadata and hydrated content where available
  - ingest manifest
- Generate or update wiki pages for:
  - session summaries
  - source pages
  - claim pages
  - finding pages
  - gap/question pages
  - concept/entity stubs
- Write graph nodes and edges into SQLite.
- Update `wiki/index.md` and append an ingest event to `wiki/log.md`.
- Add non-fatal post-run integration after `materialize_research_run_output()`.

## Implementation Notes

- The initial compiler should be deterministic and should not require an LLM.
- Use existing fields from `ResearchSession.metadata["analysis"]`, `metadata["validation"]`, source `query_provenance`, and source metadata.
- Store claim support from `cross_reference_claims`, finding evidence URLs, and source provenance.
- Mark weak or missing evidence as `unsupported` or `needs_review` rather than omitting the claim.
- Fail closed: if ingest errors, report a warning and keep the research run successful.
- Avoid rewriting operator-edited wiki prose in this task; append structured sections or update generated blocks only.

## Test Plan

- Fixture-based ingest from a saved session with:
  - multiple sources
  - query provenance
  - findings
  - claims
  - gaps
  - validation output
- Idempotency test: ingesting the same session twice does not duplicate graph nodes or pages.
- Raw snapshot tests confirm original session/report payloads are preserved.
- Missing report test still creates session/source/claim pages.
- Corrupt or sparse metadata test degrades gracefully with lint warnings.

## Acceptance Criteria

- Saved sessions can be ingested manually and through post-run output materialization.
- Ingest creates raw snapshots, wiki pages, graph records, index updates, and log entries.
- Every claim page has source provenance or an explicit unsupported status.
- Re-ingest is deterministic and idempotent.
- Ingest failure does not fail the parent research run.

## Verification Commands

```bash
uv run pytest tests/test_session_store.py tests/test_research_run_service.py -x
uv run pytest tests/test_orchestrator.py -x
uv run ruff check src/cc_deep_research/research_runs src/cc_deep_research/knowledge tests/
```

## Risks

- Overwriting hand-edited wiki content would make the system hard to trust. Use generated blocks or conservative merge rules.
- Ingest can grow large quickly if full source content is copied without limits. Store manifests and size caps explicitly.
