# Phase 05 - Dashboard State And Client Split

## Functional Feature Outcome

The dashboard has feature-scoped state and API clients instead of one large content-gen store and one large content-gen client.

## Why This Phase Exists

The frontend currently mirrors backend coupling. `useContentGen` owns unrelated domains, and `content-gen-api.ts` contains all content-gen endpoint wrappers. This makes large pages harder to simplify and makes frontend tests more workflow-heavy than necessary.

## Scope

- Split content-gen API clients by feature.
- Split state/actions into feature-scoped stores or hooks.
- Extract action hooks from large pages and components.
- Keep existing routes and visual behavior stable.

## Tasks

| Task | Summary |
| --- | --- |
| [P5-T1](../tasks/phase-05/p5-t1-split-content-gen-api-client.md) | Split pipeline, backlog, briefs, scripts, strategy, publish, and maintenance API clients. |
| [P5-T2](../tasks/phase-05/p5-t2-split-content-gen-store.md) | Replace the monolithic `useContentGen` store with feature stores/hooks. |
| [P5-T3](../tasks/phase-05/p5-t3-extract-large-component-actions.md) | Move mutation/loading logic out of large content-gen pages and panels into hooks. |
| [P5-T4](../tasks/phase-05/p5-t4-add-focused-frontend-store-tests.md) | Add tests for store reducers/actions and API error handling without relying only on Playwright. |
| [P5-T5](../tasks/phase-05/p5-t5-run-dashboard-regression-suite.md) | Run dashboard build, lint, and targeted Playwright workflows for content-gen, backlog, briefs, and telemetry. |

## Dependencies

- Backend route payloads should be stable after Phase 04.
- Dashboard e2e fixtures should be updated before store splitting.
- No route path changes should happen during this phase.

## Exit Criteria

- Content-gen frontend state is separated by domain.
- Large pages depend on focused hooks rather than one global content-gen store.
- Existing dashboard workflows continue to pass.
- API error handling remains consistent.
