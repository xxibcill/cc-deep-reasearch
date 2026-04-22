# P4-T1 - Add Content-Gen Contract Fixtures

## Outcome

Content-gen JSON payload shapes are protected by golden contract fixtures.

## Scope

- Add fixtures for `PipelineContext`.
- Add fixtures for backlog items and scoring output.
- Add fixtures for managed briefs and revisions.
- Add fixtures for scripting results and strategy memory.

## Implementation Notes

- Store fixtures where backend and dashboard tests can reference them when practical.
- Keep fixtures minimal but representative.
- Include legacy/backward-compatible fields when persisted data depends on them.

## Acceptance Criteria

- Contract tests fail on accidental payload shape changes.
- Fixtures cover key dashboard-facing content-gen payloads.
- Fixtures are documented enough for future updates.

## Verification

- Run content-gen contract tests.
