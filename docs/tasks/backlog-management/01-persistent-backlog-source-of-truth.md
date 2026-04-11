# Task 01: Establish Persistent Backlog Source Of Truth

Status: Planned

Phase:
Phase 1 - Backlog Visibility

Goal:
Make the dedicated backlog-management feature explicitly use the persistent managed backlog from `BacklogService` instead of pipeline-local context.

Primary files:
- `src/cc_deep_research/content_gen/backlog_service.py`
- `src/cc_deep_research/content_gen/router.py`
- `dashboard/src/app/content-gen/page.tsx`
- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`

Scope:
- Confirm that `/api/content-gen/backlog` is the canonical read path for backlog management.
- Treat `pipelineContext.backlog` as stage output for pipeline review, not the operator backlog source of truth.
- Document or encode this separation clearly enough that later tasks do not reintroduce mixed data sources.
- Remove any page-level assumptions that backlog management requires an active pipeline selection.

Acceptance criteria:
- The backlog-management plan and implementation point at one canonical backlog source.
- The dashboard no longer frames backlog management as pipeline-dependent.
- Pipeline detail keeps its stage output view without becoming the management source of truth.

Validation:
- Manual route review for `/content-gen`, `/content-gen/backlog`, and `/content-gen/pipeline/[id]`.

Out of scope:
- New API shapes
- UI create or edit flows
- Test coverage
