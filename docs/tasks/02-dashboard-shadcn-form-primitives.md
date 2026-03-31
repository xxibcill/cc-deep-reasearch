# 02. Dashboard shadcn Form Primitives

Status: Planned

## Goal

Create a consistent form vocabulary for the dashboard so inputs, labels, helper text, errors, and boolean controls stop being hand-assembled in each screen.

## Scope

- Add shared field-level wrappers and conventions on top of the base primitives
- Normalize label, description, helper, and error presentation
- Provide a migration path for both compact and full-width forms

## Non-Goals

- Migrating every form in this task
- Introducing a heavyweight form-state library

## Work

- Create shared building blocks such as:
  - `FormField`
  - `FormMessage`
  - `FormSection`
  - optional `FieldHint` or `FieldMeta`
- Standardize checkbox-row styling for settings toggles
- Standardize compact select and number-input styling
- Document how the dashboard should render:
  - field label
  - optional description
  - inline validation
  - disabled and overridden states

## Acceptance Criteria

- At least one clean shared pattern exists for text, textarea, select, checkbox, and numeric fields
- Follow-on tasks can migrate forms with minimal local styling
- Settings and content-studio surfaces can share the same field shell without losing readability

## Likely Files

- new files under `dashboard/src/components/ui/`
- `dashboard/src/app/globals.css`
- `DESIGN_SYSTEM_EXTRACTION_PLAN.md`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
