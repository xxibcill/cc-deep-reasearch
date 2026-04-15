# Phase 06 - Harden, Migrate, And Roll Out

## Functional Feature Outcome

Persistent brief management is backward-compatible, observable, tested, and safe to roll out for real operator use.

## Why This Phase Exists

This change cuts across storage, pipeline execution, APIs, and the dashboard, which means rollout risk is real. Existing saved runs, CLI flows, and operator habits cannot all change at once. This phase covers migration, failure recovery, observability, testing, and operational documentation so the system behaves predictably when mixed old and new data coexist and when long-lived dashboard sessions encounter conflicts or partial failures.

## Scope

- Add backward-compatible migration and fallback behavior for old saved runs and inline-only briefs.
- Add observability, tests, and recovery behavior for persistence and editing failures.
- Document the rollout, operator rules, and guardrails for approving and reusing briefs.

## Tasks

| Task | Summary |
| --- | --- |
| [P6-T1](./p6-t1-backward-compatibility-and-data-migration.md) | Migrate existing data and preserve compatibility during the transition to managed briefs. |
| [P6-T2](./p6-t2-observability-tests-and-failure-recovery.md) | Add observability, automated tests, and failure-recovery coverage for the new brief system. |
| [P6-T3](./p6-t3-operator-docs-rollout-and-guardrails.md) | Document rollout guidance, operator workflows, and governance guardrails. |

## Dependencies

- Earlier phases must already define the final storage, API, and dashboard behavior being hardened.
- Migration and rollout must account for existing saved jobs, stage panels, and any CLI checkpoint outputs.

## Exit Criteria

- Old pipeline data remains readable and operators can transition without data loss.
- Persistent brief management has meaningful test and observability coverage.
- Operators have clear documentation for how to edit, approve, and apply briefs safely.
