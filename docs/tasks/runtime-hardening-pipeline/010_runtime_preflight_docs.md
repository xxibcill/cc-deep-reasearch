# Task 010: Document Runtime Preflight And Safe Validation

Status: Planned

## Objective

Give contributors a repeatable, low-cost workflow to validate the pipeline before running live research queries.

## Scope

- document the recommended fast test commands for schema, provider replay, orchestrator smoke, and CLI smoke coverage
- document which checks are cheap enough to run before every significant pipeline change
- explain the remaining gaps that still require manual or live-provider validation
- link the docs to the new task-pack deliverables and test entrypoints

## Target Files

- `README.md`
- `docs/`
- `docs/tasks/runtime-hardening-pipeline/README.md`

## Dependencies

- [008_cli_fixture_smoke_command.md](008_cli_fixture_smoke_command.md)
- [009_failure_path_regressions.md](009_failure_path_regressions.md)

## Acceptance Criteria

- contributors have one documented preflight sequence to run before expensive research commands
- the docs distinguish fixture-backed confidence from live-provider confidence
- residual live-runtime risks are explicit instead of implicit

## Suggested Verification

- review the docs from the perspective of a contributor who wants to avoid wasting provider credits
