# P14-T1 - Migrate Dashboard Off Unified Content-Gen Store

## Functional Feature Outcome

Dashboard content-gen components depend on focused state stores, reducing duplicated client behavior and making future UI changes safer.

## Why This Task Exists

`useContentGen.ts` still acts as a broad compatibility store while feature stores such as `usePipeline` and `useBacklog` already exist. Several components continue to import the unified store, so actions and state normalization are repeated in more than one place. This slows frontend refactors and increases the chance that one UI path sees stale behavior.

## Scope

- List current `useContentGen` consumers and classify each by feature area.
- Migrate pipeline components to pipeline-focused hooks where equivalent behavior exists.
- Migrate backlog and brief components to focused hooks where practical.
- Keep temporary compatibility selectors only for components that need more backend or UI work.
- Add tests for migrated hook behavior and critical component flows.

## Current Friction

- `useContentGen` duplicates actions already represented in focused stores.
- Components mix broad store access with feature-specific store access.
- `dashboard/src/types/content-gen.ts` is large and manually mirrors backend stage and payload assumptions.

## Implementation Notes

- Migrate one feature area at a time to keep regressions easy to isolate.
- Prefer preserving component props and visible behavior during store migration.
- Do not remove the unified store until all imports are gone or compatibility users are documented.
- Keep API type changes separate from visual redesign.

## Test Plan

- Add or update hook tests for pipeline and backlog store behavior.
- Add component tests for migrated panels where test infrastructure already exists.
- Add a contract check for content-gen stage order and key payload fields.
- Run dashboard lint and typecheck.

## Acceptance Criteria

- Selected high-traffic components no longer import `useContentGen` when focused stores provide equivalent behavior.
- Duplicate action implementations are removed or reduced.
- Compatibility-only store responsibilities are documented.
- Dashboard typecheck and relevant tests pass.

## Verification Commands

```bash
cd dashboard && npm run typecheck
cd dashboard && npm test -- --run
uv run pytest tests/test_dashboard_content_gen_types.py -x
```

## Risks

- Store migration can create subtle stale-state bugs. Migrate by feature area and keep tests close to user workflows.
- Removing compatibility actions too early can break components that still rely on combined state. Keep a temporary compatibility layer until imports are gone.
