# P11-T1 - Tighten Content-Gen Router Composition

## Functional Feature Outcome

Content-gen routes are easier to test and maintain because dependency wiring is centralized and route handlers remain thin.

## Why This Task Exists

`content_gen/router.py` still constructs services and dependencies inside handler bodies, including config loading, audit stores, backlog services, brief services, and AI helper agents. Some services already exist, but the router remains a service locator in several paths. That makes it hard to swap test doubles, increases route test setup cost, and spreads construction policy across many handlers.

## Scope

- Identify inline dependency construction in content-gen route handlers.
- Move construction into a shared composition path used by `register_content_gen_routes()`.
- Keep route signatures and payload contracts stable.
- Convert behavior-heavy route tests into service tests where appropriate.
- Keep route tests for authentication, status codes, serialization, and path contracts.

## Current Friction

- Handlers call `load_config()` and construct stores or services in multiple places.
- Brief, backlog, strategy, scripting, and maintenance behavior is split between services and route bodies.
- Route tests need too much runtime context when they only need to verify HTTP behavior.

## Implementation Notes

- Keep the first pass local to content-gen routing and service construction.
- Prefer explicit composed dependencies passed to handlers through closures or app state.
- Do not change route URLs, method names, request models, or response models.
- Avoid global singletons that would make tests order-dependent.

## Test Plan

- Add or update route tests using test-specific composed services or temp stores.
- Add service tests for behavior moved out of route handlers.
- Run dashboard content-gen API contract tests if present.
- Run existing content-gen route tests before and after each extraction step.

## Acceptance Criteria

- Route handlers no longer perform repeated config, audit, store, or agent construction.
- Route tests can exercise HTTP contracts with deterministic local dependencies.
- Service tests cover moved business behavior.
- Existing content-gen dashboard requests keep working without client changes.

## Verification Commands

```bash
uv run pytest tests/test_content_gen_routes.py tests/test_content_gen_api_services.py -x
uv run ruff check src/cc_deep_research/content_gen/router.py src/cc_deep_research/content_gen/*_service.py
```

## Risks

- Centralized composition can become another large object if it absorbs behavior. Keep it to construction and wiring.
- Route closures may capture stale state in tests. Prefer explicit fresh construction per app instance.
