# Task 013: Slim Orchestrator Facade

Status: Done

## Objective

Turn the top-level orchestrator into a thin composition layer over the existing `orchestration/` services.

## Scope

- move remaining orchestration details out of `TeamResearchOrchestrator`
- keep the public `execute_research()` contract stable
- reduce callback plumbing and state mutation in the façade

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/execution.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/runtime.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/session_state.py`

## Dependencies

- [001_add_refactor_safety_net.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/001_add_refactor_safety_net.md)
- [007_add_models_compatibility_layer.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/007_add_models_compatibility_layer.md)

## Acceptance Criteria

- `TeamResearchOrchestrator` mostly wires together focused services
- phase-specific behavior moves behind explicit service boundaries
- orchestrator tests remain green without large fixture rewrites

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py tests/test_teams.py`
