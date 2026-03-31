# 04. Dashboard shadcn Home And Session List

Status: Planned

## Goal

Standardize the home page and session list so cards, filters, selection controls, action rows, and empty states use the shared component layer.

## Scope

- `HomePage`
- `SessionList`
- session filter controls
- session card action patterns

## Non-Goals

- Changing pagination behavior
- Reworking session data contracts

## Work

- Replace session-card checkboxes with shared `Checkbox`
- Replace search and filter controls with shared form primitives
- Normalize session-card actions onto `Button` variants
- Replace repeated pill styling with shared badges where appropriate
- Convert empty/loading/error states to shared card and alert patterns

## Acceptance Criteria

- `session-list.tsx` stops hand-styling controls that already exist in `ui/`
- Filter bar markup is materially smaller and easier to maintain
- Session-card actions and statuses use consistent shared primitives

## Likely Files

- `dashboard/src/app/page.tsx`
- `dashboard/src/components/session-list.tsx`
- `dashboard/src/components/ui/*`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
- `02-dashboard-shadcn-form-primitives.md`
- `03-dashboard-shadcn-start-research-form.md`
