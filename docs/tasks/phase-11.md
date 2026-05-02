# Phase 11 - Content-Gen Router Composition Boundary

## Functional Feature Outcome

Content-gen HTTP routes become thin adapters over explicitly composed services instead of constructing config, stores, audit objects, and agents inside route handlers.

## Why This Phase Exists

The content-gen router has already started moving workflow behavior into services, but handler-level dependency construction remains scattered through the route module. This keeps HTTP tests heavier than necessary and makes business behavior harder to exercise without FastAPI. This phase finishes the composition boundary: routes should validate requests, call composed services, and serialize responses, while service construction happens in one predictable place.

## Scope

- Move repeated config, store, audit, service, and agent construction out of route handlers.
- Preserve existing route paths, request bodies, response shapes, and dashboard behavior.
- Keep route handlers focused on HTTP concerns and service calls.
- Add route contract tests plus service tests for behavior moved out of the router.

## Tasks

| Task | Summary |
| --- | --- |
| [P11-T1](../tasks/phase-11/p11-t1-tighten-content-gen-router-composition.md) | Tighten content-gen router dependency composition so handlers stop constructing workflow services directly. |

## Dependencies

- Existing content-gen services such as backlog, brief, scripting, maintenance, and strategy services should remain the preferred behavior owners.
- Dashboard API clients must remain compatible with current route paths and response shapes.
- Test fixtures should provide temp stores or fake services without live provider credentials.

## Exit Criteria

- Content-gen route handlers no longer construct core stores, audit stores, config objects, or agents inline except through a shared composition path.
- Route tests focus on HTTP contract behavior.
- Service tests cover behavior that was previously only reachable through route tests.
- Existing dashboard content-gen flows remain compatible.
