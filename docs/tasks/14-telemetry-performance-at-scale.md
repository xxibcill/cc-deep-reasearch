# Task 14: Improve Telemetry Performance At Scale

## Goal

Keep the telemetry workspace responsive when sessions contain large event volumes and complex derived views.

## Depends On

- Tasks 01 through 13 complete

## Primary Areas

- `dashboard/src/components/session-details.tsx`
- `dashboard/src/lib/telemetry-transformers.ts`
- `dashboard/src/components/telemetry/event-table.tsx`
- `dashboard/src/components/agent-timeline.tsx`
- `dashboard/src/components/workflow-graph.tsx`
- `dashboard/src/components/decision-graph.tsx`
- `dashboard/src/hooks/useDashboard.ts`

## Problem To Solve

As sessions get larger, the monitor can become expensive:

- filtering and derived-state computation can be repeated too often
- heavy graphs and tables can slow the workspace
- the operator experience degrades exactly when a complex run most needs inspection

## Required Changes

1. Profile and reduce avoidable recomputation in the session workspace.
2. Improve rendering behavior for large event lists and graph-heavy views.
3. Ensure filter changes, tab switches, and event selection remain responsive on larger sessions.
4. Document any intentional event caps or degraded rendering behavior if needed.

## Implementation Guidance

- Prefer targeted optimizations, not broad speculative refactors.
- Use the project’s existing React patterns rather than adding memoization everywhere blindly.
- Consider virtualization or incremental rendering if the current event table becomes a bottleneck.
- Keep correctness of filtered and derived views ahead of micro-optimizations.

## Out Of Scope

- backend event storage redesign
- changing event semantics
- removing existing telemetry views

## Acceptance Criteria

- Large historical sessions remain usable.
- Core interactions stay responsive enough for practical debugging.
- No correctness regressions in filtering, event ordering, or derived summaries.

## Verification

- Test with a large session fixture or recorded session.
- Compare responsiveness before and after for filtering, tab changes, and graph selection.
- Run any relevant dashboard tests affected by refactors.
