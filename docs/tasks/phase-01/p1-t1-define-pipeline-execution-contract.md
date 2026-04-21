# P1-T1 - Define Pipeline Execution Contract

## Outcome

`ContentGenPipeline` has a documented public execution contract before implementation moves out of the legacy orchestrator.

## Scope

- Define full pipeline run inputs and outputs.
- Define single-stage execution behavior.
- Define resume, cancellation, progress callback, and seeded context behavior.
- Define which dependencies are injected, mocked, or loaded internally.

## Implementation Notes

- Keep compatibility with existing route callers.
- Include `PipelineContext`, stage indexes, stage labels, and run constraints in the contract.
- Avoid designing around private helpers in `legacy_orchestrator.py`.

## Acceptance Criteria

- The interface supports current pipeline route behavior.
- The interface supports tests without real LLM calls.
- Known compatibility requirements are explicit.

## Verification

- Review current callers of `ContentGenOrchestrator` and confirm the contract covers them.
