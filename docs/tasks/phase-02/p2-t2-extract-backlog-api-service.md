# P2-T2 - Extract Backlog API Service

## Outcome

Backlog route behavior is owned by a focused API service.

## Scope

- Move create, list, update, select, archive, delete, and start preparation logic.
- Keep request validation models in the route layer unless shared elsewhere.
- Preserve legacy input field normalization.
- Preserve current response shapes.

## Implementation Notes

- Reuse `BacklogService` where it already owns domain behavior.
- Add a route-facing service only for HTTP workflow composition.
- Keep persistence paths configurable through the existing config.

## Acceptance Criteria

- Backlog route handlers are thin.
- Backlog API service tests cover all mutations and error cases.
- Dashboard backlog workflows continue to work.

## Verification

- Run backlog service tests and dashboard backlog e2e coverage.
