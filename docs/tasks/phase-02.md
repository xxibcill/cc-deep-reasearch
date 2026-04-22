# Phase 02 - Content-Gen API Service Split

## Functional Feature Outcome

Content-gen HTTP routes become thin adapters over focused application services.

## Why This Phase Exists

`content_gen/router.py` currently mixes request models, route handlers, config loading, store construction, pipeline jobs, WebSocket progress, JSON serialization, backlog logic, brief lifecycle behavior, strategy operations, scripting, maintenance, and AI helper endpoints. This makes route tests large and makes business logic hard to test without FastAPI.

## Scope

- Extract content-gen services by workflow area.
- Keep FastAPI request and response handling in the router.
- Move behavior into testable Python services.
- Standardize JSON serialization at route boundaries.

## Tasks

| Task | Summary |
| --- | --- |
| [P2-T1](../tasks/phase-02/p2-t1-extract-pipeline-run-service.md) | Move pipeline start, resume, stop, job registry updates, progress events, and seeded backlog starts into a pipeline run service. |
| [P2-T2](../tasks/phase-02/p2-t2-extract-backlog-api-service.md) | Move backlog create/list/update/select/archive/delete/start behavior behind a backlog API service. |
| [P2-T3](../tasks/phase-02/p2-t3-extract-brief-api-service.md) | Move brief list/create/update/revision/approve/archive/clone/branch behavior into a brief API service. |
| [P2-T4](../tasks/phase-02/p2-t4-extract-strategy-scripting-maintenance-services.md) | Split strategy, scripting, publish queue, audit, and maintenance endpoints into focused services. |
| [P2-T5](../tasks/phase-02/p2-t5-shrink-content-gen-router-tests.md) | Move behavior assertions from route tests into service tests and leave route tests for HTTP contracts. |

## Dependencies

- Phase 01 pipeline boundary should be stable.
- Current route payloads must remain compatible with dashboard clients.
- Existing dirty edits in `content_gen/router.py` need to be integrated carefully.

## Exit Criteria

- `register_content_gen_routes()` primarily validates requests, calls services, and returns responses.
- Service tests cover core content-gen behavior without FastAPI.
- Existing dashboard content-gen workflows still pass.
