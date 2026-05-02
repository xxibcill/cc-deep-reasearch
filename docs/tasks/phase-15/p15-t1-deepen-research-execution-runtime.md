# P15-T1 - Deepen Research Execution Runtime

## Functional Feature Outcome

Research execution changes can be made through focused orchestration services while the public orchestrator remains a stable facade.

## Why This Task Exists

`TeamResearchOrchestrator` now delegates to several orchestration services, but it still builds execution hooks and exposes compatibility methods that execution depends on. That means some runtime behavior is split between the facade and the services. Deepening this boundary will make staged workflow changes easier to reason about, especially source collection, analysis, monitor events, and degraded-state handling.

## Scope

- Inventory behavior currently passed from `TeamResearchOrchestrator` into execution hooks.
- Move service-owned behavior into orchestration services where practical.
- Preserve public method names and saved session behavior.
- Add tests around execution service behavior using mocked LLM and search edges.
- Keep planner and staged workflow compatibility intact.

## Current Friction

- `TeamResearchOrchestrator` initializes many services but also keeps compatibility attributes and adapter methods.
- `ResearchExecutionService` accepts a hook bundle for core runtime callbacks.
- `AnalysisWorkflow` still reaches into analyzer internals for LLM client behavior.
- Source collection coordinates search, hydration, and fallback behavior across several collaborators.

## Implementation Notes

- Treat this as a boundary-deepening task, not a rewrite.
- Preserve the public orchestrator facade for callers and tests that still construct it directly.
- Move one callback responsibility at a time and add tests around the receiving service.
- Keep external providers mocked or faked in all new tests.

## Test Plan

- Add or extend tests for `ResearchExecutionService` with fake planning, phase, and source collaborators.
- Add tests for analysis workflow degraded behavior and missing LLM client cases.
- Add tests for source collection fallback and hydration metadata.
- Run route and session tests to protect saved research output.

## Acceptance Criteria

- At least one major execution-hook responsibility moves behind a focused orchestration service.
- Public orchestrator behavior remains compatible.
- New service-level tests cover successful execution and degraded/fallback behavior.
- Existing saved session and route tests pass.

## Verification Commands

```bash
uv run pytest tests/test_research_run_service.py tests/test_web_server_research_run_routes.py tests/test_session_store.py -x
uv run mypy src/cc_deep_research/orchestration src/cc_deep_research/research_runs
```

## Risks

- Moving runtime callbacks can change monitor event order or saved session metadata. Assert observable metadata and lifecycle events in tests.
- Some tests may rely on facade methods directly. Keep public compatibility while moving implementation ownership behind services.
