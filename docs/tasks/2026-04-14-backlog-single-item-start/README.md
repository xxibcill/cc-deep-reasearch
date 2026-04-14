# Backlog Single-Item Start Task Pack

## Goal

Add an explicit operator action that starts the content-generation pipeline from one existing backlog item.

The operator should be able to trigger this from:

- the backlog overview page
- the backlog detail page

The action should create a pipeline run focused on that one item and then take the operator to the pipeline detail view.

## Product Intent

This feature is not "click a row and magic happens."

The repo already uses row and card click to navigate from backlog overview to backlog details. That behavior should remain unchanged. Starting work on a backlog item is a consequential action with cost and side effects. It needs an explicit button or menu action.

For v1, the safest mental model is:

1. The operator reviews a backlog item.
2. The operator explicitly clicks `Start Production`.
3. The system creates a new pipeline run seeded with that item as the selected primary lane.
4. The run begins at `generate_angles` and proceeds through the downstream production stages.
5. When scripting completes, existing pipeline behavior marks the item `in_production`.

## Why This Shape Fits The Existing Repo

- The dashboard already has both backlog overview and detail routes:
  - `dashboard/src/app/content-gen/backlog/page.tsx`
  - `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx`
- The backend already supports asynchronous pipeline jobs with job registry, events, and pipeline detail pages.
- The orchestrator already supports starting from a later stage when the context is already populated.
- The orchestrator already knows how to derive lane candidates from `selected_idea_id` and `active_candidates`.
- The scripting stage already marks an item `in_production` through `BacklogService`.

The missing piece is not a new pipeline engine. The missing piece is a narrow entrypoint that seeds a valid context for a single backlog item and reuses the existing pipeline machinery.

## Recommended V1 Behavior

### Operator-facing behavior

- Add a `Start Production` action to each item on the backlog overview page.
- Add a prominent `Start Production` action to the backlog detail page action rail.
- Keep row/card click behavior unchanged. It should still open the detail page.
- After the operator clicks the action, create a new pipeline run and navigate to `/content-gen/pipeline/{pipeline_id}`.

### Backend behavior

- Add a dedicated endpoint:
  - `POST /api/content-gen/backlog/{idea_id}/start`
- Do not overload the generic `POST /api/content-gen/pipelines` contract for v1.
- Load the requested backlog item.
- Seed a minimal but valid `PipelineContext` for one item.
- Run the existing orchestrator with:
  - `initial_context=<seeded ctx>`
  - `from_stage=4` (`generate_angles`)
  - `to_stage=<default final stage unless future UI needs a custom end stage>`

### Context behavior

The seeded context should treat the item as the primary selected candidate. It should not attempt to regenerate backlog ideation or re-score the entire backlog.

## Why Start At `generate_angles`

The pipeline stage order is:

1. `load_strategy`
2. `plan_opportunity`
3. `build_backlog`
4. `score_ideas`
5. `generate_angles`
6. `build_research_pack`
7. `build_argument_map`
8. `run_scripting`
9. downstream production stages

The start-from-backlog flow already has a chosen item. Re-running:

- `build_backlog` would be redundant and potentially destructive because it regenerates backlog ideas from theme-level inputs.
- `score_ideas` would re-rank the backlog and may override the operator’s explicit choice.

Starting at `generate_angles` preserves the operator’s selected item while still using the full downstream production pipeline.

## Explicit Non-Goals

Do not expand this feature into any of the following in the same slice:

- changing row click to start pipeline
- generalized "start from any stage" UX from backlog pages
- multi-select backlog start
- bulk production launch from the backlog page
- replacing the current generic pipeline start form
- re-architecting the pipeline job registry
- turning standalone scripting into the primary entrypoint

## Key Decisions

### Decision 1: Explicit action, not implicit row click

Chosen because:

- current row click already navigates to details
- starting a pipeline has side effects
- accidental launches would be expensive and confusing

### Decision 2: Dedicated endpoint, not an expanded generic start route

Chosen because:

- the generic start route currently accepts `theme`, `from_stage`, and `to_stage`
- overloading it with backlog-item-specific semantics would make the API harder to reason about
- a dedicated route maps directly to the product action

### Decision 3: Seed `PipelineContext`, then reuse `run_full_pipeline`

Chosen because:

- the repo already has a stable async execution path for pipeline jobs
- the resume path already demonstrates `initial_context`-based execution
- this keeps observability, pipeline pages, and event publishing consistent

### Decision 4: Let existing scripting logic mark `in_production`

Chosen because:

- existing pipeline behavior already calls `BacklogService.mark_in_production(...)`
- a new early status transition would introduce additional semantics that are not needed for v1

## Files That Matter

- `dashboard/src/app/content-gen/backlog/page.tsx`
- `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx`
- `dashboard/src/components/content-gen/backlog-panel.tsx`
- `dashboard/src/hooks/useContentGen.ts`
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/types/content-gen.ts`
- `src/cc_deep_research/content_gen/router.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/backlog_service.py`
- `tests/test_content_gen.py`
- `tests/test_web_server.py`
- `dashboard/tests/e2e/backlog-management.spec.ts`

## Proposed Task Breakdown

1. Backend route and seeded-context execution path
2. Frontend action wiring on overview and detail pages
3. Duplicate-run guard and UX conflict handling
4. Tests and manual verification

## Task Files

- `01-backend-contract.md`
- `02-frontend-workflow.md`
- `03-context-seeding-and-pipeline-lifecycle.md`
- `04-tests-and-ship-checklist.md`

## Advice For The Implementer

- Keep v1 narrow. The point is to start one existing item safely, not to invent a new orchestration layer.
- Preserve the current backlog browsing behavior.
- Reuse the pipeline job and event machinery exactly where possible.
- Make duplicate-run handling explicit. Silent duplicate launches will create confusing operator state.
- Bias toward deterministic validation over convenience.
