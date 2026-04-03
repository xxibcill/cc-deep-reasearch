# Task 02: Add Pipeline Stage Tracing (Partially Implemented)

## Status

Current status: Partially implemented

Implemented today:

- `PipelineStageTrace` exists in `src/cc_deep_research/content_gen/models.py`.
- `PipelineContext` stores `stage_traces`.
- The orchestrator records compact input/output summaries and appends traces for completed and skipped stages.
- `tests/test_content_gen.py` covers trace serialization and skipped-stage recording.

Remaining gaps:

- Failed stages are not appended to `stage_traces`; `_run_stage` re-raises before writing a failed trace record.
- Warning and decision fields are only lightly used today.
- The tests do not cover a real failed-stage trace path.

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

- `PipelineContext` stores a list of stage traces
- traces are appended as stages complete
- failed or skipped stages can still be represented
- serialization round-trip works

## Testing

Add tests for:

- trace model serialization
- orchestrator appends traces in stage order
- output summaries exist for at least backlog and scoring
- skipped stages are recorded correctly when prerequisites are missing

## Notes For Small Agent

Prefer compact summaries over raw prompt or raw response storage in this task.
