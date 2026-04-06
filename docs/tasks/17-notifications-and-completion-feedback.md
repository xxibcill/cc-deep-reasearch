# Task 17: Add Better Notifications And Completion Feedback

Status: Done

## Goal

Improve immediate feedback for long-running operations so operators know when important actions succeed, fail, or require follow-up.

## Depends On

- Tasks 01 through 16 complete

## Primary Areas

- `dashboard/src/components/start-research-form.tsx`
- `dashboard/src/components/run-status-summary.tsx`
- `dashboard/src/components/session-telemetry-workspace.tsx`
- `dashboard/src/components/session-list.tsx`
- shared notification primitives under `dashboard/src/components/ui/` if needed

## Problem To Solve

Long-running and destructive actions need clearer feedback:

- run start confirmation may be too abrupt
- completion or failure may require manual checking
- archive, restore, delete, and settings saves benefit from a more coherent notification model

## Required Changes

1. Add consistent inline or toast-style feedback for key operations:
   - start run
   - run completion/failure
   - archive/restore/delete
   - settings save
2. Make feedback actionable where possible, for example:
   - open monitor
   - open report
   - retry
3. Keep noise low. Do not create a chatty notification system.

## Implementation Guidance

- Use a single consistent feedback pattern rather than one-off alerts everywhere.
- Prefer ephemeral notifications for success and persistent ones for failures or actions requiring attention.
- Respect the operator workflow; avoid blocking modals unless necessary.

## Out Of Scope

- browser push notifications
- email/slack integration
- multi-user notification preferences

## Acceptance Criteria

- Important operations have clear feedback and next steps.
- Success feedback is lightweight; failure feedback is explicit.
- Notification behavior feels consistent across the dashboard.

## Verification

- Test success and failure cases for run start, delete/archive/restore, and settings save.
- Confirm feedback does not stack awkwardly or obscure critical UI.
