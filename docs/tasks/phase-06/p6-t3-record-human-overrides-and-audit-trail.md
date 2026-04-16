# P6-T3 - Record Human Overrides And Audit Trail

## Objective

Persist the operator decisions that override automated gates so publish risk and postmortem review stay auditable.

## Scope

- store override actor, time, reason, and linked evidence
- attach overrides to managed briefs, release states, and publish queue items
- surface override history in operator-facing docs and dashboard views

## Affected Areas

- `src/cc_deep_research/content_gen/brief_service.py`
- `src/cc_deep_research/content_gen/storage/publish_queue.py`
- `docs/brief-management.md`
- `docs/content-generation.md`

## Dependencies

- P6-T2 must define the release-state model

## Acceptance Criteria

- every override is persisted with reason and timestamp
- audit history is available at publish and performance review time
- operators can distinguish normal approvals from exception-based releases
