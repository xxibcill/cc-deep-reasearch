# P7-T1 - Capture Always-On Performance Signals

## Objective

Persist the signals needed to evaluate both content performance and workflow speed on every run.

## Scope

- capture publish outcome, response metrics, cycle time, and stage-level timing together
- link performance data back to idea score, content type, effort tier, and release state
- make the data available to both CLI reports and dashboard views

## Affected Areas

- `src/cc_deep_research/content_gen/agents/performance.py`
- `src/cc_deep_research/telemetry/`
- `docs/TELEMETRY.md`
- `docs/content-generation.md`

## Dependencies

- earlier phases must emit consistent timing, decision, and release-state metadata

## Acceptance Criteria

- every published asset can be traced back to its selection and production decisions
- performance analysis includes throughput context, not only audience metrics
- stage timing is reliable enough to measure workflow speed
