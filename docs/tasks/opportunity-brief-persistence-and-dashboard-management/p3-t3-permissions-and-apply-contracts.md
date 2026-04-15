# Task P3-T3: Permissions And Apply Contracts

## Objective

Define the mutation rules that separate advisory AI behavior from explicit operator-approved persistence.

## Scope

- Clarify which routes are read-only, proposal-only, or state-mutating.
- Add apply-style contracts for AI-assisted changes.
- Define validation and authorization boundaries for edit, approve, archive, and clone operations.
- Ensure brief mutations follow the same trust model across dashboard and API consumers.

## Acceptance Criteria

- AI-generated proposals never persist automatically.
- Operators have a clear apply step for material brief changes.
- The API surface makes mutation intent obvious enough to support auditing and safe UI behavior.

## Advice For The Smaller Coding Agent

- Match the backlog advisory/apply pattern wherever the workflow is similar.
- Avoid clever hybrid routes that both generate advice and sometimes persist, depending on flags.
