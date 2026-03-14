# Task 044: Migrate Secondary LLM Consumers And Update Docs

Status: Complete

## Objective

Finish the first agent-level routing slice by migrating the next LLM consumer after analysis and documenting the mixed-route behavior for operators and contributors.

## Scope

- migrate `ReportQualityEvaluatorAgent` to the shared routing layer
- keep heuristic fallback behavior
- document `llm` config usage and mixed-session behavior
- add focused mixed-route integration tests

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/report_quality_evaluator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/config.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/README.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_report_quality_evaluator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`

## Dependencies

- [042_analysis_service_llm_router_integration.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/042_analysis_service_llm_router_integration.md)
- [043_llm_route_telemetry_and_session_metadata.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/043_llm_route_telemetry_and_session_metadata.md)

## Acceptance Criteria

- report quality evaluation resolves its route through the shared routing layer
- docs explain how planner-selected agent routes interact with Claude CLI, OpenRouter, and Cerebras
- tests cover at least one mixed session where analysis uses one route and report evaluation uses another
- docs no longer imply Claude-only LLM behavior in the active path

## Exit Criteria

- the first end-to-end LLM-routing slice covers more than one agent consumer
- contributors have documentation and tests for the new architecture

## Suggested Verification

- run `uv run pytest tests/test_report_quality_evaluator.py tests/test_orchestrator.py`
