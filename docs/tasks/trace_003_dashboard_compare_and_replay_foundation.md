# Task 003: Add Operator Panels, Run Compare, And Replay Foundation

Status: Done

## Objective

Turn the richer backend trace data into an operator-facing workflow that quickly shows the run story, root causes, state changes, and degraded areas. Establish the first usable compare and replay foundation without attempting a full deterministic simulator in one pass.

## Scope

- add new dashboard panels for narrative, cause chain, state changes, and failures/degradations
- add a minimal compare flow for two runs
- define and implement a portable trace bundle export format
- lay the groundwork for offline replay by capturing enough context for later fixture-based reproduction

## Dashboard Work

Add or update UI surfaces so an operator can inspect:

- run narrative
- key decisions and why they were made
- state changes in chronological order
- failures and degradations with scope and severity
- run-over-run deltas for the most important metrics

The first compare version can be simple. It should at least show:

- duration delta
- source-count delta
- token delta
- route delta
- degraded reason delta
- failure count delta

## Trace Bundle Work

Define a portable export shape that includes:

- session summary
- ordered events
- saved session summary or payload reference
- config snapshot
- artifact references and hashes
- trace schema version

Do not require full provider-response capture in this task, but leave a clear extension point for fixture references or captured responses later.

## Target Files

- `dashboard/src/components/session-details.tsx`
- `dashboard/src/components/session-list.tsx`
- `dashboard/src/lib/telemetry-transformers.ts`
- `dashboard/src/lib/api.ts`
- `dashboard/src/types/telemetry.ts`
- `dashboard/src/hooks/useDashboard.ts`
- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/cli/session.py`
- `src/cc_deep_research/session_store.py`

## Implementation Notes

- keep the first compare flow focused on operator usefulness, not perfect analytics completeness
- prefer a side-by-side summary with expandable details over a complex visualization
- trace bundle export should be explicit and stable enough to use in future replay tooling and CI fixtures
- avoid coupling compare mode to only browser-started runs; saved historical sessions should work too
- do not let replay concerns block the UI work; export format first, replay harness later

## Acceptance Criteria

- the dashboard exposes dedicated views for narrative, cause chain, state diff, and failures/degradations
- an operator can select two runs and see metric and outcome deltas in one place
- the backend or CLI can export a portable trace bundle for a completed session
- exported bundles include enough metadata to support later fixture-based replay and regression comparison

## Suggested Verification

- add frontend coverage for new response types and compare rendering where the repo already tests UI helpers
- add API coverage in `tests/test_web_server.py`
- add session-store or CLI coverage for bundle export
- manually compare two completed sessions with different degraded outcomes

## Dependencies

- `trace_001_trace_contract_hardening.md`
- `trace_002_derived_trace_api_and_history.md`

## Out Of Scope

- full deterministic replay engine
- CI golden-trace regression gate
- exhaustive cross-run statistical analytics
