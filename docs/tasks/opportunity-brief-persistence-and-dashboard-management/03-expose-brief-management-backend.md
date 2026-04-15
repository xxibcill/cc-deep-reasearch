# Phase 03 - Expose Brief Management Backend

## Functional Feature Outcome

The backend exposes a safe, auditable API surface for listing, editing, approving, versioning, and applying brief changes.

## Why This Phase Exists

Once a brief is a persisted resource, operators need the same backend reliability and explicit mutation semantics that backlog already has. This phase creates the management API, conflict controls, and governance hooks that stop the feature from becoming an ad hoc collection of write paths. It also sets the rule that AI is advisory first and persistence happens only through explicit apply routes.

## Scope

- Add CRUD, detail, revision, approval, and status routes for persistent briefs.
- Add audit history, optimistic concurrency, and change visibility for operator trust.
- Define mutation and AI-apply contracts so write paths stay explicit and reviewable.

## Tasks

| Task | Summary |
| --- | --- |
| [P3-T1](./p3-t1-brief-management-api.md) | Add the first-class backend API for brief management and lifecycle operations. |
| [P3-T2](./p3-t2-audit-history-and-conflict-control.md) | Add revision audit history and conflict control for concurrent editing. |
| [P3-T3](./p3-t3-permissions-and-apply-contracts.md) | Define explicit write and apply semantics for operator and AI-assisted mutations. |

## Dependencies

- Phases 01 and 02 must provide stable storage and pipeline linkage semantics.
- Audit and telemetry conventions should remain compatible with existing backlog governance patterns.

## Exit Criteria

- The backend exposes a coherent brief management surface separate from pipeline run inspection.
- Operators can inspect revision and approval history instead of guessing from raw payloads.
- No brief mutation path bypasses explicit validation and persistence rules.
