# 05. Dashboard shadcn Settings Forms

Status: Planned

## Goal

Move the settings editor and secret editor onto shared shadcn field patterns so the settings surface no longer carries a private form system.

## Scope

- `ConfigEditor`
- `ConfigSecretsPanel`
- route and override fields
- secret replace flows

## Non-Goals

- Changing backend config behavior
- Redefining which fields are editable

## Work

- Replace repeated text inputs, selects, numeric inputs, and checkbox rows with shared primitives
- Introduce a reusable field shell for:
  - label
  - description
  - overridden state
  - effective versus persisted values
  - error text
- Normalize secret replace textareas and password inputs onto shared form components
- Reduce per-field class duplication in `config-editor.tsx`

## Acceptance Criteria

- Settings forms share the same control vocabulary as the rest of the dashboard
- Overridden-field UX remains clear after the refactor
- Secret replace flows remain masked and readable

## Likely Files

- `dashboard/src/components/config-editor.tsx`
- `dashboard/src/components/config-secrets-panel.tsx`
- `dashboard/src/app/settings/page.tsx`
- `dashboard/src/components/ui/*`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
- `02-dashboard-shadcn-form-primitives.md`
