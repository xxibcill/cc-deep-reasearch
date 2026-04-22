# P1-T4 - Add Pipeline Boundary Tests

## Outcome

The content-gen pipeline can be refactored internally while behavior is protected at the public boundary.

## Scope

- Test full-run happy path with mocked stage dependencies.
- Test cancellation.
- Test resume from a stage.
- Test seeded backlog item starts.
- Test stage skip/block behavior.

## Implementation Notes

- Prefer observable `PipelineContext` and trace assertions over private helper assertions.
- Use fake agents or stage adapters instead of real provider calls.
- Replace redundant legacy helper tests once boundary tests exist.

## Acceptance Criteria

- Boundary tests fail when stage sequencing or trace behavior regresses.
- Tests do not require real LLM, search, or network access.
- Tests are stable enough for normal CI.

## Verification

- Run the new pipeline test file and relevant content-gen route tests.
