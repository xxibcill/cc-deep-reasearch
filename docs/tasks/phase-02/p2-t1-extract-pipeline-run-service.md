# P2-T1 - Extract Pipeline Run Service

## Outcome

Pipeline job orchestration is testable outside FastAPI route handlers.

## Scope

- Move pipeline start, stop, resume, and status behavior into a service.
- Move job registry updates and progress event publishing behind the service boundary.
- Move seeded backlog item start behavior into the same service or a collaborator.
- Preserve WebSocket progress behavior.

## Implementation Notes

- Keep the route responsible for HTTP request parsing and status codes.
- Inject `PipelineRunJobRegistry`, `EventRouter`, and pipeline factory.
- Keep cancellation behavior observable in tests.

## Acceptance Criteria

- Pipeline routes call service methods instead of embedding orchestration logic.
- Service tests cover successful run, cancellation, duplicate active item, and resume.
- Existing response payloads remain compatible.

## Verification

- Run pipeline service tests and content-gen pipeline route tests.
