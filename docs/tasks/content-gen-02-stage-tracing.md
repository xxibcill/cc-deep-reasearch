# Task 02: Add Pipeline Stage Tracing

## Status

Current status: Done

Implemented:

- `PipelineStageTrace` exists in `src/cc_deep_research/content_gen/models.py`.
- `PipelineContext` stores `stage_traces`.
- The orchestrator records compact input/output summaries and appends traces for completed, skipped, and failed stages.
- `tests/test_content_gen.py` covers trace serialization, skipped-stage recording, and failed-stage recording.
- Added `test_failed_stage_is_recorded_in_traces` to verify failed stages are recorded.

## Goal

Add structured stage traces to the full content-generation pipeline.

## Why

Scripting already has step traces. The rest of the content pipeline does not. That makes early-stage failures and weak outputs hard to inspect.

## Scope

In scope:

- add `PipelineStageTrace`
- add optional per-stage warnings and decisions
- persist traces in `PipelineContext`
- record stage start/end and duration
- add compact input/output summaries

Out of scope:

- WebSocket event changes
- dashboard rendering

## Suggested File Targets

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `tests/test_content_gen.py`

## Suggested Trace Shape

- `stage_index`
- `stage_name`
- `stage_label`
- `status`
- `started_at`
- `completed_at`
- `duration_ms`
- `input_summary`
- `output_summary`
- `warnings`
- `decision_summary`

## Acceptance Criteria

- [x] `PipelineContext` stores a list of stage traces
- [x] traces are appended as stages complete
- [x] failed or skipped stages can still be represented
- [x] serialization round-trip works

## Testing

Tests added for:

- [x] trace model serialization
- [x] orchestrator appends traces in stage order
- [x] output summaries exist for at least backlog and scoring
- [x] skipped stages are recorded correctly when prerequisites are missing
- [x] failed stages are recorded in stage_traces

## Notes For Small Agent

Prefer compact summaries over raw prompt or raw response storage in this task.
