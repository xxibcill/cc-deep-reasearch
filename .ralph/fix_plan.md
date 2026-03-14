# Ralph Development Plan

## Status: IN PROGRESS

## Completed Tasks
- [x] Task 036: Establish LLM Route Contract And Config - DONE
- [x] Task 037: Add Session-Scoped LLM Route Registry - DONE
- [x] Task 038: Extract Claude CLI Transport Adapter - DONE
- [x] Task 039: Add OpenRouter LLM Adapter - DONE
- [x] Task 040: Add Cerebras LLM Adapter - DONE
- [x] Task 041: Let Planner Emit Agent LLM Plan - DONE
- [x] Task 042: Route Analysis Through Shared LLM Layer - DONE
- [x] Task 043: Record LLM Route Telemetry and Session Metadata - DONE

## Remaining Tasks
- [ ] Task 044: Migrate Secondary LLM Consumers and Update Docs

## Implementation Summary

### Task 036: LLM Route Contract and Config
- Created `/src/cc_deep_research/llm/base.py` with:
  - `LLMTransportType` enum (CLAUDE_CLI, OPENROUTER_API, CEREBRAS_API, HEURISTIC)
  - `LLMProviderType` enum (CLAUDE, OPENROUTER, CEREBRAS, HEURISTIC)
  - `LLMRoute` model for route configuration
  - `LLMRoutePlan` model for per-agent route plans
  - `LLMRequest` and `LLMResponse` normalized models
  - Exception taxonomy (LLMError, LLMTimeoutError, LLMAuthenticationError, etc.)
  - `BaseLLMTransport` abstract class for transport adapters
- Added LLM config tree to `config.py`:
  - `LLMClaudeCLIConfig`, `LLMOpenRouterConfig`, `LLMCerebrasConfig`
  - `LLMRouteDefaults` for per-agent defaults
  - `LLMConfig` main config with `get_enabled_transports()` and `get_route_for_agent()`
- Added route models to `models.py`:
  - `LLMTransportType`, `LLMProviderType`, `LLMRouteModel`, `LLMPlanModel`
  - Updated `StrategyResult` to include optional `llm_plan` field

### Task 037: Session-Scoped LLM Route Registry
- Created `/src/cc_deep_research/llm/registry.py` with:
  - `LLMRouteRegistry` class for late-bound route lookup
  - Methods: `get_route()`, `set_route()`, `update_from_plan()`, `get_available_route()`
  - Telemetry callback support
  - Nested session protection for Claude CLI

### Task 038: Claude CLI Transport Adapter
- Created `/src/cc_deep_research/llm/claude_cli.py` with:
  - `ClaudeCLITransport` implementing `BaseLLMTransport`
  - Async `execute()` method for LLM requests
  - Streamed subprocess telemetry (stdout/stderr chunks)
  - Nested session detection
  - Timeout and error handling with mapped exceptions

### Task 039: OpenRouter LLM Adapter
- Created `/src/cc_deep_research/llm/openrouter.py` with:
  - `OpenRouterTransport` implementing `BaseLLMTransport`
  - Async `execute()` method using httpx for API calls
  - OpenAI-compatible request format with system prompt support
  - HTTP error mapping (401→Auth, 429→RateLimit, 400/500→Provider)
  - Timeout handling with `httpx.TimeoutException`
  - Request error handling with `httpx.RequestError`
  - Telemetry callback integration
  - Extra headers support for custom configurations
- Created `/tests/test_llm_openrouter.py` with:
  - 30 tests covering success, error, and edge cases
  - Mock httpx client for testing without network calls
  - Tests for authentication, rate limiting, timeout, and provider errors

### Task 040: Cerebras LLM Adapter
- Created `/src/cc_deep_research/llm/cerebras.py` with:
  - `CerebrasTransport` implementing `BaseLLMTransport`
  - Async `execute()` method using httpx for API calls
  - OpenAI-compatible request format (same as OpenRouter)
  - HTTP error mapping (401→Auth, 429→RateLimit, 400/500→Provider)
  - Timeout handling with `httpx.TimeoutException`
  - Request error handling with `httpx.RequestError`
  - Telemetry callback integration
  - Default model: llama-3.3-70b
- Created `/tests/test_llm_cerebras.py` with:
  - 29 tests covering success, error, and edge cases
  - Mock httpx client for testing without network calls
  - Tests for authentication, rate limiting, timeout, and provider errors

### Task 041: Planner Agent LLM Plan
- Created `/src/cc_deep_research/orchestration/llm_route_planner.py` with:
  - `LLMRoutePlanner` class for route planning
  - Transport availability inspection (Claude CLI, OpenRouter, Cerebras)
  - Per-agent route assignment based on agent type
  - Fallback order building from available transports
  - Registry update from plan output
  - Fast API preferred for analyzer/deep_analyzer/validator agents
- Updated `/src/cc_deep_research/orchestration/planning.py`:
  - `ResearchPlanningService` now accepts optional config and registry
  - `analyze_strategy()` creates LLM plan and updates registry
- Created `/tests/test_llm_route_planner.py` with:
  - 24 tests covering planning, availability, and route assignment
  - Tests for nested session constraint, fallback order, and agent routing

### Task 042: Route Analysis Through Shared LLM Layer
- Created `/src/cc_deep_research/llm/router.py` with:
  - `LLMRouter` class for unified transport selection and execution
  - `get_transport()` method for agent-specific transport resolution
  - `execute()` method for async LLM operations with fallback
  - Transport caching for performance
  - Heuristic fallback when no transports available
  - Support for system prompts and model overrides
- Updated `/src/cc_deep_research/llm/__init__.py`:
  - Exported `LLMRouter` class
- Created `/tests/test_llm_router.py` with:
  - 13 tests covering routing, execution, and fallback behavior
  - Mock registry for testing without real routes
  - Tests for transport caching, error handling, and heuristic fallback

## Tests Passing
- 495 tests passing across all test files (126 LLM/config tests, 24 planner tests, 13 router tests)

## Next Steps
Continue with Task 043 (Record LLM Route Telemetry and Session Metadata) in next loop.

### Task 043: Record LLM Route Telemetry and Session Metadata
- Updated `/src/cc_deep_research/monitoring.py`:
  - `record_llm_route_selected()`: Records when an LLM route is selected for an agent
  - `record_llm_route_fallback()`: Records when an LLM route fallback occurs
  - `record_llm_route_request()`: Records the start of an LLM request through a route
  - `record_llm_route_completion()`: Records the completion of an LLM request through a route
  - `_build_llm_route_summary()`: Builds summary of route usage from telemetry events
  - `finalize_session()`: Now includes `llm_route` summary with transport/provider/agent stats
- Updated `/src/cc_deep_research/orchestration/session_state.py`:
  - `LLMRouteRecord`: Dataclass for recording route assignments
  - `LLMRouteUsageStats`: Dataclass for tracking route usage statistics
  - `llm_planned_routes`: Tracks routes planned by the planner
  - `llm_actual_routes`: Tracks routes actually used during execution
  - `llm_route_usage`: Tracks per-route usage statistics
  - `llm_fallback_events`: Records fallback events
  - `set_llm_planned_route()`: Records a planned route for an agent
  - `set_llm_actual_route()`: Records actual route used for an agent
  - `record_llm_route_usage()`: Records usage stats for a route
  - `record_llm_route_fallback()`: Records a fallback event
  - `get_llm_route_summary()`: Returns summary of LLM route usage
  - `build_metadata()`: Now includes `llm_routes` in session metadata
- Updated `/src/cc_deep_research/telemetry.py`:
  - `_build_llm_route_streams()`: Builds LLM route analytics from telemetry events
  - `query_live_llm_route_analytics()`: Returns LLM route analytics for a live session
  - `query_llm_route_analytics()`: Returns LLM route analytics from DuckDB
  - `query_llm_route_summary()`: Returns summary of route usage (live or DB)
  - `query_live_session_detail()`: Now includes `llm_route_analytics` field
  - Added exports to `__all__` for new functions
- Updated `/src/cc_deep_research/dashboard_app.py`:
  - `_render_llm_route_analytics()`: Renders LLM route analytics pane in dashboard
  - `run_dashboard()`: Now calls LLM route analytics renderer after subprocess detail
  - `export_payload`: Now includes `llm_route_analytics` in download
- Created tests in `/tests/test_monitoring.py`:
  - 7 tests for LLM route telemetry events in `TestLLMRouteTelemetry` class
- Created tests in `/tests/test_telemetry.py`:
  - 2 tests for LLM route analytics queries

## Tests Passing
- 64 tests passing (62 existing + 2 new LLM route analytics tests)

## Next Steps
Continue with Task 044 (Migrate Secondary LLM Consumers and Update Docs) in next loop.
