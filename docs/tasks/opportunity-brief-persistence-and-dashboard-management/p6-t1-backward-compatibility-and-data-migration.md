# Task P6-T1: Backward Compatibility And Data Migration

## Objective

Roll the managed brief system out without breaking existing saved pipeline jobs, inline brief payloads, or operator workflows.

## Scope

- Add compatibility logic for old pipeline jobs and dashboard payloads.
- Define migration behavior for existing generated briefs and saved runs.
- Decide how CLI outputs and checkpoint files behave during the transition.
- Provide safe fallback behavior when a managed brief record is missing or partially migrated.

## Acceptance Criteria

- Historical pipeline runs remain readable.
- Operators do not lose access to earlier opportunity briefs during rollout.
- The system can recover gracefully when managed brief links are missing or stale.

## Advice For The Smaller Coding Agent

- Bias toward compatibility shims before destructive migration.
- Make degraded compatibility states visible so operators know when they are viewing legacy data.
