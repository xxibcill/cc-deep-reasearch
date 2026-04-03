# Task 06: Expose Pipeline Traces in the Dashboard (Done)

## Status

Current status: Done

Verified against the current codebase on 2026-04-03.

Implemented today:

- `dashboard/src/types/content-gen.ts` now includes backend-aligned degraded-state and shortlist-selection fields on `BacklogOutput`, `ScoringOutput`, and `PipelineContext`.
- `dashboard/src/lib/content-gen-api.ts` now seeds those explicit shortlist-selection fields in the empty dashboard pipeline context.
- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx` now prefers backend `selected_idea_id`, `shortlist`, `runner_up_idea_ids`, and `selection_reasoning` over inferred list position.
- The pipeline detail page now surfaces pipeline-level selection rationale and degraded-stage reasons directly in the scoring and backlog panels.
- `dashboard/tests/e2e/content-gen-observability.spec.ts` now type-checks the dashboard fixture against `PipelineContext` and covers degraded-state messaging plus backend-driven selection rationale rendering.

## Goal

Show richer stage traces and decisions in the content-gen dashboard.

## Why

Once traces and live events exist, operators need a usable view of them.

## Scope

In scope:

- surface stage trace summaries
- show warnings, skips, and decisions
- show selected idea rationale and shortlist context
- keep the current page structure intact if possible

Out of scope:

- full redesign of content-gen pages
- metrics analytics beyond the current run

## Suggested File Targets

- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`
- `dashboard/src/components/content-gen/`
- `dashboard/src/types/content-gen.ts`

## Acceptance Criteria

- current pipeline page can render stage trace summaries
- operator can see why a stage was skipped or degraded
- operator can inspect the chosen idea and alternates

## Testing

Add tests for:

- type alignment with backend response
- rendering trace warnings and statuses
- rendering selected-idea rationale when present

## Notes For Small Agent

Preserve existing page flow. Add visibility before adding new controls.
