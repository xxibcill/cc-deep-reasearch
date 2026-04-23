# Phase 00 - Baseline And Refactor Safety

## Functional Feature Outcome

The team has a clean, repeatable baseline for safely refactoring the project without losing existing behavior or uncommitted work.

## Why This Phase Exists

This project already has active uncommitted edits and several large, coupled surfaces. Before changing architecture, we need a known test, lint, and build baseline, a map of current failures, and a safe way to distinguish regressions from pre-existing issues.

## Scope

- Preserve current dirty work in `content_gen/progress.py`, `content_gen/router.py`, and `tests/test_web_server.py`.
- Record Python and dashboard quality baselines.
- Identify generated files and local artifacts that should not influence refactor diffs.
- Define the first set of architectural boundaries to protect during migration.

## Tasks

| Task | Summary |
| --- | --- |
| [P0-T1](../tasks/phase-00/p0-t1-capture-working-tree-baseline.md) | Capture current dirty state, branch status, and generated artifacts before refactor work begins. |
| [P0-T2](../tasks/phase-00/p0-t2-record-quality-baseline.md) | Run or document `pytest`, `ruff`, dashboard lint/build, and known failures. |
| [P0-T3](../tasks/phase-00/p0-t3-map-refactor-boundaries.md) | Produce a short dependency map for content-gen, API routes, dashboard stores, and model contracts. |

## Dependencies

- Current uncommitted work must be preserved.
- Dependency install state must be known for Python and dashboard checks.
- No architectural edits should start until known test failures are recorded.

## Exit Criteria

- Current worktree changes are documented and not overwritten.
- Baseline checks are recorded with pass/fail status.
- First refactor boundary is selected: content-gen pipeline execution.
