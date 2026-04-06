# Task 11: Improve Search Cache Operations And Observability

Status: Done

## Goal

Make search-cache tooling feel like a useful operational feature instead of a secondary maintenance panel.

## Depends On

- Tasks 01 through 10 complete

## Primary Areas

- `dashboard/src/components/search-cache-panel.tsx`
- `dashboard/src/types/search-cache.ts`
- `dashboard/src/lib/api.ts`
- `dashboard/src/app/settings/page.tsx`

## Problem To Solve

The search cache is operationally important, but the dashboard likely presents it as a thin utility:

- stats are available, but decisions are not guided
- purge/delete actions can feel high-risk without enough framing
- operators may not understand when cache issues explain stale or surprising results

## Required Changes

1. Improve the cache panel so it answers:
   - how big the cache is
   - whether it is healthy/useful
   - what the operator can safely clean up
2. Add clearer safety framing for destructive cache actions.
3. Improve result listing or summary views so operators can connect cache state to research behavior.
4. Align styling and interaction quality with the rest of the dashboard.

## Implementation Guidance

- Preserve all existing cache actions.
- Prefer lightweight guidance and better summaries over adding many new controls.
- If confirmation is required for destructive actions, make the impact explicit.
- Keep the panel useful for both casual and power users.

## Out Of Scope

- backend cache redesign
- new cache storage engines
- advanced analytics beyond current API support

## Acceptance Criteria

- The cache panel feels operator-friendly and lower-risk.
- Users can understand what cache maintenance actions do before triggering them.
- Existing cache operations still work.

## Verification

- Test stats loading, list loading, purge/delete/clear flows, and empty states.
- Confirm destructive-action messaging is explicit and accurate.
