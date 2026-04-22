# Phase 06 - Quality Gates And Long-Term Cleanup

## Functional Feature Outcome

The refactored architecture is protected by stricter checks and a clear cleanup path for remaining legacy compatibility.

## Why This Phase Exists

The repo has strict mypy settings but currently ignores errors globally. After the structural refactor, new boundaries should be held to a higher standard without forcing a whole-repo type cleanup in one risky pass.

## Scope

- Enable stricter checks incrementally for new and refactored modules.
- Remove dead compatibility paths only after contracts prove they are unused.
- Track remaining monoliths and oversized tests as explicit follow-up work.
- Keep CI focused on preventing regression at boundaries.

## Tasks

| Task | Summary |
| --- | --- |
| [P6-T1](../tasks/phase-06/p6-t1-enable-mypy-for-refactored-modules.md) | Add mypy overrides so new service and pipeline modules are checked before the whole repo is ready. |
| [P6-T2](../tasks/phase-06/p6-t2-tighten-ruff-ignores-in-new-code.md) | Keep existing ignores for legacy code but require cleaner lint behavior in new modules. |
| [P6-T3](../tasks/phase-06/p6-t3-remove-unused-legacy-content-gen-paths.md) | Remove or quarantine legacy content-gen code once compatibility imports are no longer needed. |
| [P6-T4](../tasks/phase-06/p6-t4-document-architecture-boundaries.md) | Update architecture docs to describe pipeline, route service, model contract, and dashboard state boundaries. |
| [P6-T5](../tasks/phase-06/p6-t5-create-refactor-regression-checklist.md) | Create a short regression checklist for future feature work touching these boundaries. |

## Dependencies

- Phases 01-05 should be complete.
- Contract tests must be stable.
- Legacy import usage must be measured before removal.

## Exit Criteria

- New and refactored modules are covered by stricter typing or lint rules.
- Remaining legacy paths are either removed or documented with owners.
- Architecture docs match actual code structure.
- Future changes have a clear regression checklist.
