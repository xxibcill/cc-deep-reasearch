# Task 037: Add Session-Scoped LLM Route Registry

Status: Complete

## Objective

Introduce a late-bound session registry for LLM routes so agent execution can change per session without rebuilding the runtime after planning.

## Scope

- add a dedicated `llm` package for routing primitives
- add a session-scoped route registry
- initialize the registry in orchestrator runtime startup
- expose route lookup to agents or shared services
- do not add planner-owned route selection yet

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/base.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/registry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/runtime.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/session_state.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_runtime.py`

## Dependencies

- [036_llm_route_contract_and_config.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/036_llm_route_contract_and_config.md)

## Acceptance Criteria

- runtime creates one route registry per session
- registry can return a default route for a given agent id
- registry supports post-start updates without re-instantiating agents
- orchestrator reset and shutdown clear session-scoped route state cleanly

## Exit Criteria

- the runtime has a real late-binding seam for planner-selected agent routes
- subsequent tasks can update routes after planning without constructor mutation hacks

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_runtime.py`
