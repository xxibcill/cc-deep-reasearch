# P18-T5: Lazy Telemetry Derivations

## Summary

Move expensive telemetry derivation work out of the default render path and compute only the structures needed by the active monitor view.

## Details

1. Audit `dashboard/src/components/session-details.tsx` and `dashboard/src/lib/telemetry-transformers.ts` for repeated derivations on the same event set.
2. Split `deriveTelemetryState()` into smaller derivation helpers for counts, filter options, graph, timeline, tool executions, LLM reasoning, and event index.
3. Compute lightweight counts and filter options for the default monitor screen.
4. Compute graph, timeline, tool, LLM, and decision structures only when the active view or detail tab needs them.
5. Debounce or transition expensive filter updates so typing and select changes remain responsive.
6. Consider a Web Worker for large-session derivations if profiling shows the main thread still blocks.

## Acceptance Criteria

- The default monitor view no longer computes every derived structure when only summary counts and event rows are visible.
- Filtering events does not recompute graph and timeline data unless those views are active.
- Large-session filter latency is measurably lower than the baseline from P18-T1.
- Operator insights, stats cards, filters, tool detail, LLM detail, and prompt detail continue to show correct data.
- Focused transformer tests cover the split derivation helpers.
