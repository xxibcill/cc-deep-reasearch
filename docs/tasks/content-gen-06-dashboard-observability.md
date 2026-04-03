# Task 06: Expose Pipeline Traces in the Dashboard (Not Implemented)

## Status

Current status: Not implemented

Evidence in the current codebase:

- The dashboard has basic progress UI, but it does not render `stage_traces`, warnings, skips, or decision summaries.
- `dashboard/src/types/content-gen.ts` does not model `OpportunityBrief`, `PipelineStageTrace`, or `PipelineContext.stage_traces`.
- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx` still uses a 12-stage label list and omits `plan_opportunity`.
- The current pipeline page does not expose selected-idea rationale, shortlist context, or trace details.

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
