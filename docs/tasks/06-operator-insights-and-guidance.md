# Task 06: Add Higher-Level Operator Insights And Guidance

## Goal

Reduce the amount of raw telemetry interpretation required by surfacing concise explanations of session state, likely issues, and recommended next actions.

## Depends On

- Tasks 01 through 05 complete

## Primary Areas

- `dashboard/src/components/session-details.tsx`
- `dashboard/src/components/session-telemetry-workspace.tsx`
- `dashboard/src/lib/telemetry-transformers.ts`
- `dashboard/src/components/telemetry/*`
- `dashboard/src/types/telemetry.ts` if new derived UI types are needed

## Problem To Solve

The dashboard already exposes detailed telemetry, but operators still need to infer answers to questions such as:

- why is this run slow
- where did it fail
- is it degraded or simply incomplete
- what should I inspect next

## Required Changes

1. Add an operator summary layer above or alongside the detailed telemetry explorer.
2. The summary should translate raw event data into plain operational conclusions such as:
   - run is active and healthy
   - run appears stalled
   - failures occurred in a specific phase
   - report generation is blocked by missing artifact or terminal failure
3. Add recommended next actions based on session state, for example:
   - inspect tool failures
   - review LLM reasoning
   - open report
   - return to home and compare against a previous successful run
4. Reuse existing derived data where possible before inventing new calculations.

## Implementation Guidance

- Keep the summary concise. It should guide, not replace the detailed inspector.
- Prefer deterministic heuristics over vague narrative generation.
- Avoid adding backend work unless absolutely necessary.
- If heuristics are added in `telemetry-transformers`, make them testable and explicit.

## Out Of Scope

- AI-generated summaries
- new backend endpoints
- saved annotations or comments

## Acceptance Criteria

- Operators can answer basic “what happened” questions without scanning the full event table first.
- The summary does not conflict with or obscure the detailed telemetry tools.
- The logic is deterministic and testable.

## Verification

- Add or update tests for any new transformer logic.
- Manually inspect healthy, failed, and sparse-event sessions to confirm the summary behaves sensibly.
