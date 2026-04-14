# Task P1-T1: Superuser Triage Contract

## Objective

Add the backend contract for AI triage so a superuser can request batch backlog analysis and receive structured, reviewable proposals.

## Scope

- Introduce a dedicated triage request/response contract under the existing content-gen API.
- Support proposal types for:
  - batch enrich
  - batch reframe
  - dedupe recommendation
  - archive recommendation
  - priority recommendation
- Validate all proposed field changes before they reach `BacklogService`.
- Keep the route advisory until the operator explicitly applies changes.

## Recommended Route Shape

- `POST /api/content-gen/backlog-ai/triage/respond`
- `POST /api/content-gen/backlog-ai/triage/apply`

The exact path can be adjusted if you want to fold this into the existing backlog chat namespace, but the contract should clearly distinguish batch triage from conversational editing.

## Data Rules

- `respond` never writes.
- `apply` is the only write path.
- Bulk proposals must resolve to concrete item-level operations before apply.
- Unknown action kinds and unsupported fields must return structured errors.
- Partial apply behavior must be explicit and deterministic.

## Acceptance Criteria

- The backend can return structured batch triage proposals for a backlog snapshot.
- Apply requests are validated and persisted only through `BacklogService`.
- Invalid proposal items fail closed with operator-readable errors.

## Advice For The Smaller Coding Agent

- Reuse the existing backlog chat validation patterns where possible.
- Keep the first proposal schema narrow and deterministic.
- Bias toward explicit item-level operations over abstract AI intentions.
