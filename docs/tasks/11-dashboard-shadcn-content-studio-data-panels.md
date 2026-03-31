# 11. Dashboard shadcn Content Studio Data Panels

Status: Planned

## Goal

Refactor content-studio list, table, and expandable result panels onto shared shadcn primitives while keeping the existing data model intact.

## Scope

- `PublishQueuePanel`
- `ScriptsPanel`
- `StageResultPanel`
- related result-shell surfaces used on the pipeline detail page

## Non-Goals

- Replacing pipeline-progress visualization logic
- Redesigning stage-specific content output

## Work

- Convert `PublishQueuePanel` to a shared `Table`-based pattern
- Migrate `ScriptsPanel` and `StageResultPanel` to `Accordion` or `Collapsible`
- Replace local action buttons such as “Reuse Inputs” and row delete controls with shared button variants
- Normalize empty, loading, and expanded-detail states
- Ensure the pipeline detail page consumes the shared expandable shell cleanly

## Acceptance Criteria

- Content-studio data panels stop using one-off raw table and collapsible markup
- Expand/collapse interactions are consistent across scripts and pipeline stages
- Publish queue actions use the same shared action styles as the rest of the app

## Likely Files

- `dashboard/src/components/content-gen/publish-queue-panel.tsx`
- `dashboard/src/components/content-gen/scripts-panel.tsx`
- `dashboard/src/components/content-gen/stage-result-panel.tsx`
- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`
- `dashboard/src/components/ui/*`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
- `09-dashboard-shadcn-content-studio-shell.md`
- `10-dashboard-shadcn-content-studio-forms.md`
