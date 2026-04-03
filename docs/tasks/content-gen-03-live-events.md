# Task 03: Fix Live Pipeline Events (Partially Implemented)

## Status

Current status: Partially implemented

Implemented today:

- The router emits `pipeline_stage_started` when each stage begins.
- The orchestrator invokes `stage_completed_callback` immediately after a stage completes or is skipped.
- The router publishes `pipeline_stage_completed` per stage instead of batching completion events at the end.

Remaining gaps:

- There are no dedicated `pipeline_stage_failed` or `pipeline_stage_skipped` event types; failure and skip are folded into `stage_status`.
- The dashboard page still looks for `pipeline_stage_error`, so failed stage updates are not wired correctly on the frontend.
- There are no router-level tests asserting live event order or failure payloads.

## Goal

Make pipeline progress events actually reflect live stage completion.

## Why

The current API emits `pipeline_stage_completed` in a batch after the whole run finishes. That is not true live monitoring.

## Scope

In scope:

- emit stage completion when each stage finishes
- emit stage failure and skipped events when relevant
- attach enough metadata for the dashboard to show useful progress

Out of scope:

- full dashboard redesign
- LLM token telemetry

## Suggested File Targets

- `src/cc_deep_research/content_gen/router.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `dashboard/src/app/content-gen/pipeline/[id]/page.tsx`
- `dashboard/src/types/content-gen.ts`
- related tests

## Acceptance Criteria

- stage-completed events are published immediately after each stage
- stage-failed events include a safe error payload
- skipped stages can be surfaced without crashing the run
- frontend types remain aligned with backend payloads

## Testing

Add tests for:

- start and complete events emitted in execution order
- no end-of-run batch completion loop remains
- failed stage emits error event

## Notes For Small Agent

Do not add a new event system. Extend the current event router usage.
