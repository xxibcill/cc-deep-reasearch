# P2-T3 - Extract Brief API Service

## Outcome

Brief lifecycle behavior is testable without routing through FastAPI.

## Scope

- Move list, create, update, revision, apply, approve, archive, supersede, revert, clone, branch, sibling, compare, and audit behavior.
- Preserve lifecycle state validation.
- Preserve audit store integration.
- Preserve response payload shapes.

## Implementation Notes

- Keep `BriefService` as the domain owner where possible.
- Add a route-facing service for request-level composition and serialization.
- Avoid changing persisted brief formats in this phase.

## Acceptance Criteria

- Brief routes delegate behavior to a service.
- Service tests cover lifecycle transitions and conflict/error cases.
- Existing brief tests are moved or reduced where redundant.

## Verification

- Run brief service tests and targeted route tests.
