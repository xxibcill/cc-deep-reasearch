# Phase 03 - Core Dashboard API Route Split

## Functional Feature Outcome

The backend app composition stays in `web_server.py`, while domain routes live in focused modules.

## Why This Phase Exists

`web_server.py` is over 2,500 lines and registers config, research runs, sessions, reports, bundles, artifacts, checkpoints, resume/rerun, WebSockets, search cache, benchmarks, themes, and analytics. The app factory is doing too much, which makes route ownership and tests harder to reason about.

## Scope

- Keep `create_app()` and runtime setup in `web_server.py`.
- Move route registration into domain modules.
- Reuse existing service boundaries like `ResearchRunService`.
- Avoid changing public API paths unless explicitly planned.

## Tasks

| Task | Summary |
| --- | --- |
| [P3-T1](../tasks/phase-03/p3-t1-extract-research-run-routes.md) | Move research run start/status/stop routes into a research run router module. |
| [P3-T2](../tasks/phase-03/p3-t2-extract-session-routes.md) | Move session list/detail/delete/archive/restore/events/report/bundle/artifact/checkpoint routes into session route modules. |
| [P3-T3](../tasks/phase-03/p3-t3-extract-search-cache-and-benchmark-routes.md) | Move search cache, benchmark, theme, and analytics endpoints out of `web_server.py`. |
| [P3-T4](../tasks/phase-03/p3-t4-extract-websocket-runtime-adapter.md) | Separate WebSocket connection handling from app setup while preserving `EventRouter` behavior. |
| [P3-T5](../tasks/phase-03/p3-t5-rebalance-web-server-tests.md) | Split `test_web_server.py` into route-domain test files and service tests. |

## Dependencies

- Phase 00 baseline must identify existing `test_web_server.py` behavior.
- Public API route paths must stay stable for the dashboard.
- Existing `DashboardBackendRuntime` lifecycle behavior must be preserved.

## Exit Criteria

- `web_server.py` owns app creation, middleware, lifespan, and route composition only.
- Route modules are organized by domain.
- `test_web_server.py` is substantially smaller or split by domain.
- Dashboard e2e smoke tests still reach the same backend endpoints.
