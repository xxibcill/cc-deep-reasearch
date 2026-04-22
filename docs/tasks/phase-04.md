# Phase 04 - Model And Storage Contract Hardening

## Functional Feature Outcome

Backend and dashboard data contracts are explicit, tested, and safe to evolve.

## Why This Phase Exists

The content-gen model package has many compatibility re-exports, legacy field normalizers, and manually serialized route responses. That is reasonable during active migration, but it becomes risky when refactoring because internal model movement can accidentally break persisted data or frontend payload assumptions.

## Scope

- Define stable JSON payload contracts for content-gen, sessions, telemetry, radar, and research runs.
- Add golden tests for migration and backward compatibility cases.
- Reduce unnecessary broad imports from `content_gen.models`.
- Keep backward compatibility where persisted user data depends on it.

## Tasks

| Task | Summary |
| --- | --- |
| [P4-T1](../tasks/phase-04/p4-t1-add-content-gen-contract-fixtures.md) | Add golden fixtures for pipeline context, backlog items, managed briefs, scripting results, and strategy memory. |
| [P4-T2](../tasks/phase-04/p4-t2-add-storage-migration-contract-tests.md) | Test YAML/SQLite migration and legacy field normalization at storage boundaries. |
| [P4-T3](../tasks/phase-04/p4-t3-standardize-route-serialization.md) | Centralize model-to-JSON response helpers to reduce repeated `json.loads(model_dump_json())`. |
| [P4-T4](../tasks/phase-04/p4-t4-narrow-model-imports.md) | Replace broad model re-export reliance in internal modules with direct domain imports where practical. |
| [P4-T5](../tasks/phase-04/p4-t5-sync-dashboard-type-fixtures.md) | Align dashboard TypeScript fixtures with backend JSON contract tests. |

## Dependencies

- Phase 02 should have route services in place.
- Existing persisted formats must be inventoried before removing compatibility behavior.
- Dashboard type expectations must be checked against real backend payloads.

## Exit Criteria

- Contract tests fail clearly when payload shapes change.
- Storage migration and backward compatibility behavior is tested outside route handlers.
- New internal code imports models from narrower domain modules.
- Dashboard types match tested backend fixtures.
