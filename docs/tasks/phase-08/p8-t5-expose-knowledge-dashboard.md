# P8-T5 - Expose Knowledge Dashboard

## Functional Feature Outcome

The dashboard can inspect the local knowledge graph, open source-backed wiki pages, review lint findings, and trace how a research session contributed to accumulated knowledge.

## Why This Task Exists

The existing dashboard already has workflow and decision graph surfaces. The knowledge graph should reuse those patterns so operators can inspect accumulated knowledge without leaving the app. This is especially important for trust: users need to see which claims are supported, unsupported, stale, or contradictory.

## Scope

- Add backend routes for knowledge graph summaries, node detail, page detail, lint findings, and session contribution traces.
- Add dashboard navigation for the knowledge graph.
- Reuse existing D3 graph patterns before introducing new visualization libraries.
- Add filters for node kind, status, confidence, source type, freshness, and lint severity.
- Add inspectors for sessions, sources, claims, findings, gaps, concepts, and pages.
- Add operator actions for opening raw evidence, wiki page paths, and lint locations.

## Implementation Notes

- Keep the first graph view dense but utilitarian; this is an operator console, not a landing page.
- Avoid nested card layouts and preserve existing dashboard visual conventions.
- Large graphs need pagination, filtering, or local neighborhood expansion.
- Do not make dashboard edits mutate wiki pages until CLI and ingest merge rules are stable.
- Use graph export JSON shape from the CLI as the dashboard contract where possible.

## Test Plan

- Backend route tests for graph summary, node detail, page detail, lint findings, and missing vault behavior.
- Type tests or unit tests for graph transformers.
- Playwright coverage for graph loading, filtering, selecting nodes, and opening inspectors.
- Empty-state tests when the vault is not initialized.
- Accessibility checks for graph controls and inspectors.

## Acceptance Criteria

- Dashboard can load and filter the knowledge graph.
- Node selection opens source-backed details with page path, evidence, and related nodes.
- Lint findings are visible and link back to affected pages/nodes.
- Session detail can show knowledge outputs produced by that session.
- Missing or uninitialized knowledge vault states are handled clearly.

## Verification Commands

```bash
uv run pytest tests/test_web_server_session_routes.py tests/test_web_server_research_run_routes.py -x
cd dashboard && npm run test -- --run
cd dashboard && npm run test:e2e -- --grep "knowledge|dashboard"
```

## Risks

- Large graph rendering can become slow. Start with filtered neighborhoods and summary views.
- The dashboard can imply edit capability before merge rules are safe. Keep first release read-only.
