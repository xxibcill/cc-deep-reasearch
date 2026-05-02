# Phase 14 - Dashboard Content-Gen State Split

## Functional Feature Outcome

The dashboard uses focused content-gen stores and API contracts instead of a broad compatibility store that duplicates feature-store behavior.

## Why This Phase Exists

The dashboard has focused content-gen stores for pipeline and backlog behavior, but the older unified `useContentGen` store still duplicates many actions and remains imported by several components. At the same time, the large frontend content-gen type file manually mirrors backend contracts. This phase migrates dashboard consumers toward focused stores and hardens the frontend/backend contract so UI changes do not keep adding compatibility debt.

## Scope

- Inventory `useContentGen` consumers and group them by feature area.
- Migrate components to focused stores where equivalent behavior already exists.
- Keep a compatibility path only where migration is not yet practical.
- Add or update frontend tests around migrated hooks and API contract assumptions.
- Keep dashboard behavior and route payloads compatible with the backend.

## Tasks

| Task | Summary |
| --- | --- |
| [P14-T1](../tasks/phase-14/p14-t1-migrate-dashboard-off-unified-content-gen-store.md) | Migrate dashboard content-gen consumers from the broad compatibility store to focused feature stores. |

## Dependencies

- Backend content-gen route payloads should remain stable during this phase.
- Existing dashboard components should keep their visible behavior while store dependencies change.
- API type changes should be coordinated with backend contract tests.

## Exit Criteria

- High-traffic content-gen dashboard components use focused stores instead of duplicated `useContentGen` actions.
- The unified store is smaller, clearly compatibility-only, or has a documented removal path.
- Frontend tests cover migrated hook behavior.
- Backend and frontend content-gen stage order and payload assumptions remain aligned.
