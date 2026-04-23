# P2-T5 - Shrink Content-Gen Router Tests

## Outcome

Content-gen route tests focus on HTTP contracts while behavior tests live at service boundaries.

## Scope

- Identify tests that assert service behavior through FastAPI.
- Move behavior cases to service tests.
- Keep route tests for status codes, request validation, and response envelopes.
- Remove redundant private-helper assertions when boundary tests exist.

## Implementation Notes

- Do not reduce coverage; relocate it.
- Keep enough route coverage to catch path and serialization regressions.
- Prefer fixtures shared between route and service tests.

## Acceptance Criteria

- Route tests are smaller and easier to scan.
- Service tests cover domain decisions.
- CI runtime does not increase meaningfully.

## Verification

- Run all content-gen backend tests.
