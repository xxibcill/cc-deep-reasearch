# 08. Dashboard shadcn Session Filters And Table

Status: Done

## Goal

Migrate the session monitor’s filter and event-table surfaces onto shared shadcn primitives while keeping virtualization and graph behavior intact.

## Scope

- filter panel in `SessionDetails`
- decision-graph filter row
- event table shell
- filter chips and clear actions

## Non-Goals

- Rebuilding the virtualized event renderer
- Refactoring derived telemetry logic

## Work

- Replace filter controls with shared `Select`, buttons, separators, and badges
- Move the filter disclosure behavior to a shared collapsible or accordion pattern
- Convert filter-summary chips to a shared badge style
- Evaluate whether the event table header and row shell should use a shared `Table` wrapper while preserving virtualization
- Normalize alert and empty-state blocks around the detail panels

## Acceptance Criteria

- Session-detail filters use the same primitives as home and settings
- The filter panel is easier to scan and cheaper to maintain
- Virtualized table behavior is preserved after the visual refactor

## Likely Files

- `dashboard/src/components/session-details.tsx`
- `dashboard/src/components/ui/*`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
- `02-dashboard-shadcn-form-primitives.md`
- `07-dashboard-shadcn-session-workspace-shell.md`
