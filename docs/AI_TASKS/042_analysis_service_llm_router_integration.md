# Task 042: Route Analysis Through The Shared LLM Layer

Status: Complete

## Objective

Refactor the analysis path so `AnalyzerAgent` and `DeepAnalyzerAgent` resolve Claude CLI or API routes through the shared routing layer instead of owning Claude-specific initialization.

## Scope

- refactor `AIAnalysisService` to use the route registry and router
- migrate analyzer and deep analyzer operations first
- preserve heuristic fallback behavior
- allow mixed-session execution where different agents use different routes

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/ai_analysis_service.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/analyzer.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/deep_analyzer.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/router.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/llm/registry.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_llm_analysis_client.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`

## Dependencies

- [037_session_llm_route_registry.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/037_session_llm_route_registry.md)
- [038_claude_cli_transport_adapter.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/038_claude_cli_transport_adapter.md)
- [039_openrouter_llm_adapter.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/039_openrouter_llm_adapter.md)
- [040_cerebras_llm_adapter.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/040_cerebras_llm_adapter.md)
- [041_planner_agent_llm_routing_plan.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/041_planner_agent_llm_routing_plan.md)

## Acceptance Criteria

- analyzer and deep analyzer choose routes at execution time through the registry
- Claude CLI, OpenRouter, Cerebras, and heuristic fallback share one routing path
- mixed-session behavior is possible in tests
- no constructor-time Claude-only initialization remains in the active analysis path

## Exit Criteria

- the first real agent consumers use the new routing architecture
- one research session can mix CLI and API calls at the agent level

## Suggested Verification

- run `uv run pytest tests/test_llm_analysis_client.py tests/test_orchestrator.py`
