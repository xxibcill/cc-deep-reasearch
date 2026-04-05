# Content-Gen Dashboard Detail Upgrade Tasks

This folder breaks the dashboard detail-upgrade plan into small, ordered tasks that can be handed to separate AI workers.

## Execution Order

1. [Task 01](./01-stage-panel-foundation.md) sets up the frontend structure so later UI work does not bloat the existing page.
2. [Task 02](./02-ideation-stage-details.md) expands the early pipeline stages that already have rich data in `PipelineContext`.
3. [Task 03](./03-scripting-trace-integration.md) brings the existing scripting trace inspector into the pipeline detail page.
4. [Task 04](./04-downstream-stage-details.md) expands the later content-production stages.
5. [Task 05](./05-live-pipeline-context-updates.md) makes in-progress runs update their detail panels live instead of only after the run completes.
6. [Task 06](./06-stage-trace-enrichment.md) improves backend trace payloads so the operator UI can show better decisions, warnings, and summaries.
7. [Task 07](./07-tests-and-docs.md) adds regression coverage and updates docs after the feature work lands.

## Working Rules

- Keep each task scoped to its own file unless the task explicitly calls for broader changes.
- Do not silently fold later tasks into earlier ones. Small, reviewable changes are preferred.
- Preserve existing behavior and styling patterns unless the task explicitly asks for a UI change.
- Favor reusing existing components over inventing new ones.
- When a task changes backend payloads, keep TypeScript and Python models aligned.

## Primary Reference Files

- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`
- `dashboard/src/components/content-gen/quick-script-process-panel.tsx`
- `dashboard/src/components/content-gen/stage-trace-summary.tsx`
- `dashboard/src/types/content-gen.ts`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/router.py`
- `dashboard/tests/e2e/content-gen-observability.spec.ts`

