# Task 01: Normalize The Dashboard Visual Foundation

## Goal

Remove design-system drift and establish one consistent visual language before deeper workflow changes begin.

## Why This Task Comes First

Several dashboard surfaces still use older light `slate-*` styling while the rest of the app uses the newer dark observability system. If this is not fixed first, later session and home-page work will continue to copy inconsistent patterns.

## Primary Areas

- `dashboard/src/components/session-static-details.tsx`
- `dashboard/src/components/session-report.tsx`
- `dashboard/src/components/session-telemetry-workspace.tsx`
- `dashboard/src/components/compare-view.tsx`
- `dashboard/src/app/compare/page.tsx`
- `dashboard/src/app/globals.css`
- shared UI primitives under `dashboard/src/components/ui/` if needed

## Required Changes

1. Replace hard-coded light-theme colors such as `bg-white`, `bg-slate-*`, `text-slate-*`, `border-slate-*`, `bg-red-50`, and `bg-amber-50` with design tokens and existing utility classes used elsewhere in the dashboard.
2. Make session, report, telemetry, and compare surfaces feel like part of the same product as:
   - `dashboard/src/app/page.tsx`
   - `dashboard/src/components/app-shell.tsx`
   - `dashboard/src/components/session-page-frame.tsx`
3. Introduce shared utility classes in `globals.css` only if multiple screens need the same styling treatment.
4. Preserve semantics of success, warning, destructive, and loading states. This is a visual-system normalization task, not a behavior rewrite.

## Implementation Guidance

- Prefer token-driven classes such as `bg-surface`, `bg-surface-raised`, `border-border`, `text-foreground`, and `text-muted-foreground`.
- Keep the current dark default. Do not introduce a separate light visual path.
- Preserve readability for markdown and JSON report rendering.
- Keep contrast strong enough for the existing accessibility checks.
- If a component looks visually isolated, pull it toward the app-shell language rather than inventing another style.

## Out Of Scope

- changing session information architecture
- merging routes
- adding new product features
- redesigning the content-gen area

## Acceptance Criteria

- No obvious light-theme islands remain in session, report, telemetry, or compare views.
- Error, empty, and loading states look consistent with the rest of the dashboard.
- The compare page no longer feels like a separate app.
- Existing functionality remains unchanged.

## Verification

- Run targeted UI checks for home, compare, session details, session monitor, and session report.
- Run dashboard accessibility and smoke tests that cover shared colors and navigation.
- Manually inspect dark surfaces for contrast regressions in alerts, badges, and tabs.
