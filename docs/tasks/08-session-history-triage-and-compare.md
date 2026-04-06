# Task 08: Improve Session History, Triage, And Comparison

## Goal

Make historical session management and side-by-side comparison feel like part of the same operator workflow instead of separate secondary utilities.

## Depends On

- Tasks 01 through 07 complete

## Primary Areas

- `dashboard/src/components/session-list.tsx`
- `dashboard/src/components/compare-view.tsx`
- `dashboard/src/app/compare/page.tsx`
- `dashboard/src/hooks/useDashboard.ts`
- `dashboard/src/lib/compare-utils.ts`

## Problem To Solve

The list already supports compare mode, archive, restore, and delete, but these workflows are still fragmented:

- compare feels visually separate from the rest of the app
- history browsing is dense but not strongly oriented around triage
- operators do not get much guidance when deciding which sessions to compare

## Required Changes

1. Refine compare-mode entry and selection feedback in the session list.
2. Improve the compare page so it matches the rest of the dashboard and clearly explains what changed between two sessions.
3. Improve historical triage cues in the session list:
   - failed
   - archived
   - report-ready
   - active
4. Make compare deltas easier to interpret without requiring the user to decode raw counts.

## Implementation Guidance

- Preserve the current query-param compare route unless there is a very strong reason to change it.
- Avoid adding backend dependencies.
- Keep list actions functional while improving clarity.
- If new explanatory copy is added, keep it concise and operator-focused.

## Out Of Scope

- multi-session compare beyond two sessions
- persistent saved compare sets
- backend-generated diff reports

## Acceptance Criteria

- Compare mode is easier to enter, understand, and complete.
- The compare page feels visually integrated with the dashboard.
- Historical session cards better communicate which sessions deserve attention.

## Verification

- Test compare selection from the home page.
- Test invalid compare route handling.
- Verify archive, restore, delete, and compare continue to work together.
