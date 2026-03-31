# Dashboard shadcn Migration Plan

Status: Planned

## Goal

Migrate as much of the Next.js dashboard UI as practical onto a consistent shadcn-style component layer so forms, dialogs, tables, filters, alerts, and navigational patterns stop re-implementing the same markup and styling.

## Scope

- Replace thin custom `ui/` wrappers with stronger shadcn primitives where that improves accessibility and reuse
- Add missing shared primitives for repeated dashboard patterns
- Refactor dashboard pages and panels to consume the shared layer
- Keep bespoke visualizations custom while standardizing the shell around them
- Break the migration into small, reviewable tasks that can land incrementally

## Non-Goals

- Rebuilding D3 visualizations into generic component-library widgets
- Re-theming the entire dashboard away from its existing dark industrial visual language
- Rewriting working business logic just to satisfy a UI abstraction
- Migrating one-off visualization internals that do not benefit from shadcn

## Current State Summary

The dashboard already has a partial shadcn-style setup:

- config: `dashboard/components.json`
- current shared primitives: `dashboard/src/components/ui/`
- current design-system notes: `DESIGN_SYSTEM_EXTRACTION_PLAN.md`

What is still missing is the actual migration of repeated raw controls and repeated panel patterns across:

- home and session list flows
- settings and config forms
- session monitor filters, dialogs, and detail panels
- content studio forms, tables, and collapsible panels

## Components That Should Stay Custom

These should keep their custom rendering logic and only adopt shared shell components around them:

- `dashboard/src/components/workflow-graph.tsx`
- `dashboard/src/components/decision-graph.tsx`
- `dashboard/src/components/agent-timeline.tsx`

## Migration Order

### 1. Foundation

Create or replace the primitive layer first so downstream migrations stop copying raw HTML:

- `Button`
- `Input`
- `Textarea`
- `Label`
- `Checkbox`
- `Select`
- `Dialog`
- `AlertDialog`
- `Tabs`
- `Table`
- `Alert`
- `Accordion` or `Collapsible`
- `Separator`

### 2. Form Surfaces

These have the highest concentration of repeated raw `input`, `textarea`, and `select` markup:

- `start-research-form.tsx`
- `config-editor.tsx`
- `config-secrets-panel.tsx`
- `content-gen/start-pipeline-form.tsx`
- `content-gen/quick-script-form.tsx`
- `content-gen/strategy-editor.tsx`

### 3. List and Table Surfaces

- `session-list.tsx`
- `content-gen/publish-queue-panel.tsx`

### 4. Collapsible and Navigation Surfaces

- `content-gen/stage-result-panel.tsx`
- `content-gen/scripts-panel.tsx`
- `content-gen/content-gen-shell.tsx`
- `session-page-frame.tsx`

### 5. Status, Alerts, Empty States, and Cleanup

- `run-status-summary.tsx`
- `search-cache-panel.tsx`
- `session-details.tsx`
- `content-gen/page.tsx`
- remaining repeated badges and feedback blocks

## Task List

1. `01-dashboard-shadcn-foundation-primitives.md`
2. `02-dashboard-shadcn-form-primitives.md`
3. `03-dashboard-shadcn-start-research-form.md`
4. `04-dashboard-shadcn-home-and-session-list.md`
5. `05-dashboard-shadcn-settings-forms.md`
6. `06-dashboard-shadcn-settings-status-panels.md`
7. `07-dashboard-shadcn-session-workspace-shell.md`
8. `08-dashboard-shadcn-session-filters-and-table.md`
9. `09-dashboard-shadcn-content-studio-shell.md`
10. `10-dashboard-shadcn-content-studio-forms.md`
11. `11-dashboard-shadcn-content-studio-data-panels.md`
12. `12-dashboard-shadcn-testing-and-rollout.md`

## Success Criteria

- Raw `input`, `textarea`, `select`, `table`, and ad hoc modal markup is largely removed from app-level components
- Shared dashboard controls live under `dashboard/src/components/ui/`
- Session, settings, and content-studio surfaces use the same form and feedback vocabulary
- Accessibility improves through stronger keyboard and dialog behavior
- Visual regressions are limited because the migration is staged and test-backed
