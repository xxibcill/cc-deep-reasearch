# 03. Dashboard shadcn Start Research Form

Status: Done

## Goal

Refactor the home-page research launcher onto the shared shadcn form primitives so it becomes the reference implementation for the rest of the dashboard.

## Scope

- `StartResearchForm`
- Its advanced prompt editor section
- The enclosing card shell on the home page where needed

## Non-Goals

- Refactoring session list behavior
- Changing API request semantics

## Work

- Replace raw `textarea`, `select`, `input`, and button markup in `StartResearchForm`
- Migrate the advanced prompt area to a shared collapsible or accordion pattern if available
- Replace inline error styling with a shared alert or form-message pattern
- Normalize the submit button and reset button styling against `Button`

## Acceptance Criteria

- `start-research-form.tsx` no longer owns raw field styling
- Advanced settings use a shared interaction pattern instead of a one-off collapsible block
- The form remains functionally identical and keeps the current request payload

## Likely Files

- `dashboard/src/components/start-research-form.tsx`
- `dashboard/src/app/page.tsx`
- `dashboard/src/components/ui/*`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
- `02-dashboard-shadcn-form-primitives.md`
