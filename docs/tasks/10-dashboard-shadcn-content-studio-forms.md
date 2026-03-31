# 10. Dashboard shadcn Content Studio Forms

Status: Planned

## Goal

Move content-studio forms onto the shared field primitives so pipeline launch, quick scripting, and strategy editing stop carrying separate local form patterns.

## Scope

- `StartPipelineForm`
- `QuickScriptForm`
- `StrategyEditor`

## Non-Goals

- Changing request payloads or workflow semantics
- Refactoring result panels in the same task

## Work

- Replace raw text inputs, selects, textareas, and buttons with shared primitives
- Normalize run controls and markdown transfer blocks in `QuickScriptForm`
- Align `StrategyEditor` with the same field layout used by settings and research-launch forms
- Convert inline error and status text to shared form-message or alert patterns

## Acceptance Criteria

- Content-studio forms share the same field styling and behavior as the rest of the dashboard
- The quick-script form is materially simpler and less class-heavy
- Buttons and disabled states are consistent across content-studio forms

## Likely Files

- `dashboard/src/components/content-gen/start-pipeline-form.tsx`
- `dashboard/src/components/content-gen/quick-script-form.tsx`
- `dashboard/src/components/content-gen/strategy-editor.tsx`
- `dashboard/src/components/ui/*`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
- `02-dashboard-shadcn-form-primitives.md`
- `09-dashboard-shadcn-content-studio-shell.md`
