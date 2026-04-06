# Task 16: Expand Cross-Session Analysis Beyond Basic Compare

## Goal

Make comparison more useful by surfacing patterns across sessions, not just raw pairwise deltas.

## Depends On

- Tasks 01 through 15 complete

## Primary Areas

- `dashboard/src/components/compare-view.tsx`
- `dashboard/src/lib/compare-utils.ts`
- `dashboard/src/components/session-list.tsx`
- optional new comparison helpers or panels under `dashboard/src/components/`

## Problem To Solve

The current compare view is a good baseline, but it stops at simple A-vs-B counts:

- it does not explain whether a difference is meaningful
- it does not highlight likely causes
- it does not help operators compare against a known-good baseline

## Required Changes

1. Improve pairwise comparison summaries so they answer:
   - what changed
   - whether it likely improved or regressed
   - what the operator should inspect next
2. Add support for comparison context such as:
   - compare against the most recent successful run
   - compare against a same-query or similar-label baseline if such data is available in the list
3. Keep the current direct compare route working.

## Implementation Guidance

- Start from existing session data already loaded or fetchable through current APIs.
- Avoid inventing weak “smart” matching if the data is not reliable; use explicit heuristics.
- If baseline suggestion is added, keep the UI optional and transparent.

## Out Of Scope

- many-to-many analytics dashboards
- backend regression scoring
- statistical benchmarking frameworks

## Acceptance Criteria

- Compare results are more actionable than raw count deltas.
- Operators can more easily find a sensible baseline session to compare against.
- Existing compare entry points still work.

## Verification

- Test compare with similar sessions, clearly different sessions, and invalid baselines.
- Confirm the UI still handles missing data gracefully.
