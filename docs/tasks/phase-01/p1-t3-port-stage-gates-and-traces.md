# P1-T3 - Port Stage Gates And Traces

## Outcome

Stage prerequisites, brief gates, trace creation, decision summaries, and phase policy handling live inside the new pipeline boundary.

## Scope

- Move prerequisite checks for skipped stages.
- Move brief execution gate behavior.
- Move `PipelineStageTrace` creation and metadata.
- Move phase policy lookup and decision summaries.

## Implementation Notes

- Preserve observable trace payloads.
- Keep trace creation centralized so future stages do not reimplement it.
- Treat trace payload shape as a contract with the dashboard.

## Acceptance Criteria

- Skipped, blocked, successful, and failed stages produce expected traces.
- Dashboard-visible trace fields remain compatible.
- The legacy orchestrator no longer owns trace behavior for migrated stages.

## Verification

- Add tests for skipped and blocked stage outcomes at the pipeline boundary.
