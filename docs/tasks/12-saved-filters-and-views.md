# Task 12: Add Saved Filters And Reusable Session Views

## Goal

Allow operators to save and reuse common session-list and telemetry filter configurations.

## Depends On

- Tasks 01 through 11 complete

## Primary Areas

- `dashboard/src/hooks/useDashboard.ts`
- `dashboard/src/components/session-list.tsx`
- `dashboard/src/components/telemetry/filter-panel.tsx`
- `dashboard/src/components/session-details.tsx`
- browser storage helpers under `dashboard/src/lib/` if needed

## Problem To Solve

Frequent operators often repeat the same filters:

- active failures
- specific agents or providers
- archived runs with reports
- phase-specific telemetry inspections

Without saved views, the dashboard makes repeated triage slower than it should be.

## Required Changes

1. Add a lightweight saved-view system for:
   - session-list filters
   - telemetry filters
2. Support:
   - save current filters as a named view
   - apply a saved view
   - overwrite or delete a saved view
3. Use local persistence first unless there is already a backend-supported preferences system.
4. Keep the feature understandable and unobtrusive for users who do not need it.

## Implementation Guidance

- Start with local storage unless there is a compelling reason not to.
- Separate session-list views from telemetry views if that keeps the model clearer.
- Prevent broken state when stored filters no longer match current options.
- Keep naming and UI simple.

## Out Of Scope

- multi-user synced preferences
- sharing saved views across machines
- complex rule builders

## Acceptance Criteria

- Operators can save, apply, and delete named views without breaking existing filtering behavior.
- The feature feels lightweight and does not clutter the default UI.
- Invalid or stale saved views degrade gracefully.

## Verification

- Test create/apply/delete flows for both session-list and telemetry filters.
- Reload the browser to confirm persistence.
- Test behavior when filter options disappear or become invalid.
