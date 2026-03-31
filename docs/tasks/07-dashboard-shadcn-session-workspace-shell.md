# 07. Dashboard shadcn Session Workspace Shell

Status: Done

## Goal

Standardize the session workspace shell around shared navigation, card, tab, dialog, and status patterns without touching the custom graph internals.

## Scope

- `SessionPageFrame`
- `SessionReport`
- `RunStatusSummary`
- modal and tab usage in `SessionDetails`

## Non-Goals

- Replacing `WorkflowGraph`, `DecisionGraph`, or `AgentTimeline`
- Changing session data flow

## Work

- Replace custom nav-link button styling in `SessionPageFrame` with shared button semantics where practical
- Normalize report-page states to shared cards and alerts
- Refactor `RunStatusSummary` onto shared status, alert, and action patterns
- Upgrade event-details modal usage in `SessionDetails` to the shared dialog model
- Ensure the session shell uses one coherent tab and badge vocabulary

## Acceptance Criteria

- Session workspace chrome is visibly consistent across details, monitor, and report routes
- Run-status cards use shared feedback patterns instead of one-off styles
- Dialog and tab usage aligns with the upgraded `ui/` primitives

## Likely Files

- `dashboard/src/components/session-page-frame.tsx`
- `dashboard/src/components/session-report.tsx`
- `dashboard/src/components/run-status-summary.tsx`
- `dashboard/src/components/session-details.tsx`
- `dashboard/src/app/session/[id]/page.tsx`
- `dashboard/src/app/session/[id]/monitor/page.tsx`
- `dashboard/src/app/session/[id]/report/page.tsx`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
