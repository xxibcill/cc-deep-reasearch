# Agent-Level LLM Routing Plan

## Objective

Allow one research session to mix LLM execution paths at the agent level:

- some agents can use Claude Code CLI
- some agents can use direct API calls
- the planner decides the route for downstream agents
- initial API providers are Cerebras and OpenRouter

The first implementation should preserve the current heuristic fallback path and should not overload the existing search-provider abstraction.

## Why This Needs A New Layer

The current codebase has two separate concerns:

- search providers under [`src/cc_deep_research/providers`](../src/cc_deep_research/providers)
- analysis-time Claude CLI usage inside [`src/cc_deep_research/agents/ai_analysis_service.py`](../src/cc_deep_research/agents/ai_analysis_service.py) and [`src/cc_deep_research/agents/llm_analysis_client.py`](../src/cc_deep_research/agents/llm_analysis_client.py)

That means LLM routing is currently:

- not session-scoped
- not planner-controlled
- not agent-specific
- not reusable across Claude CLI and direct HTTP APIs

There is also one structural constraint that matters for this feature:

- agents are instantiated before strategy planning in [`src/cc_deep_research/orchestration/runtime.py`](../src/cc_deep_research/orchestration/runtime.py)

So the planner cannot safely choose per-agent execution by mutating constructor-time config after the runtime is already built. Routing has to be late-bound.

## Design Principles

1. Keep search providers and LLM providers separate.
2. Make LLM routing a session-level contract, not a global config-only toggle.
3. Let the planner choose routes for downstream agents, while agents resolve the route at execution time.
4. Preserve graceful degradation:
   - preferred route
   - fallback route(s)
   - heuristic fallback last
5. Record both planned and actual route usage in telemetry and session metadata.

## Proposed Architecture

### 1. Add a dedicated LLM subsystem

Create a new package:

- [`src/cc_deep_research/llm`](../src/cc_deep_research/llm)

Recommended modules:

- `base.py`: transport/client protocols and shared exceptions
- `models.py`: LLM route and provider models
- `registry.py`: session-scoped route registry
- `router.py`: route resolution and fallback selection
- `claude_cli.py`: Claude Code CLI transport adapter
- `openrouter.py`: OpenRouter HTTP adapter
- `cerebras.py`: Cerebras HTTP adapter

Do not place these under the search `providers/` package. That namespace is already search-specific.

### 2. Introduce a session-scoped route contract

Add new models in [`src/cc_deep_research/models.py`](../src/cc_deep_research/models.py):

- `LLMTransport`: `claude_cli`, `api`, `heuristic`
- `LLMProviderType`: `claude_code`, `openrouter`, `cerebras`, `heuristic`
- `AgentLLMRoute`: agent id, transport, provider, model, fallback chain, reason
- `SessionLLMPlan`: per-agent route map plus availability metadata

Extend existing session metadata so persisted runs show:

- planned route per agent
- actual route used per operation
- fallbacks taken
- route failures and degraded reasons

Primary integration point:

- [`src/cc_deep_research/orchestration/session_state.py`](../src/cc_deep_research/orchestration/session_state.py)

### 3. Make route selection late-bound

Add a session-scoped `LLMRouteRegistry` that is created at orchestrator startup and injected into agents or shared services.

This registry should support:

- bootstrap defaults before planning
- planner updates after strategy analysis
- per-agent lookup at execution time
- recording actual route selection and fallback usage

Primary runtime integration points:

- [`src/cc_deep_research/orchestration/runtime.py`](../src/cc_deep_research/orchestration/runtime.py)
- [`src/cc_deep_research/orchestrator.py`](../src/cc_deep_research/orchestrator.py)

## Planner Behavior

### Bootstrap rule

The planner cannot depend on a planner-produced route plan for its own first decision. Use one of these two approaches:

1. Keep `ResearchLeadAgent` heuristic in v1 and let it emit routes for downstream agents only.
2. If the lead becomes LLM-backed later, give it a separate bootstrap route from config, then let it emit the rest of the session plan.

For the first iteration, option 1 is the lower-risk path.

### Planner output

Extend [`src/cc_deep_research/agents/research_lead.py`](../src/cc_deep_research/agents/research_lead.py) and [`src/cc_deep_research/orchestration/planning.py`](../src/cc_deep_research/orchestration/planning.py) so strategy output contains an `llm_plan` for downstream agents.

Initial planner responsibility:

- inspect query complexity, depth, and time-sensitivity
- inspect route availability:
  - Claude CLI present or absent
  - running inside `CLAUDECODE`
  - API keys configured for OpenRouter and Cerebras
- assign preferred route and fallback chain per agent

## Initial Route Policy

This is a recommended starting policy, inferred from the current workflow shape:

- `lead`: heuristic in v1
- `expander`: heuristic in v1, optional Cerebras later
- `analyzer`: prefer Claude CLI, fallback OpenRouter API, then heuristic
- `deep_analyzer`: prefer Claude CLI, fallback OpenRouter API, then heuristic
- `validator`: prefer OpenRouter API, fallback Cerebras API, then heuristic
- `report_quality_evaluator`: prefer OpenRouter API, fallback heuristic

Reasoning:

- Claude CLI already exists for long-form synthesis and deep analysis
- OpenRouter is the best initial general-purpose API path
- Cerebras is a good initial low-latency API option for shorter structured tasks

If the run is inside Claude Code or Claude CLI is unavailable, the planner should automatically avoid `claude_cli` as the primary route.

## Provider Adapters

### Claude Code CLI adapter

Refactor the current CLI subprocess logic out of [`src/cc_deep_research/agents/llm_analysis_client.py`](../src/cc_deep_research/agents/llm_analysis_client.py) into a reusable transport adapter.

Keep these existing behaviors:

- streamed subprocess telemetry
- nested-session protection
- timeout handling
- prompt preview sanitization

### OpenRouter adapter

Add a direct HTTP client using `httpx` with:

- API key from config or env
- model selection from route config
- timeout and retry policy
- normalized request and response envelope
- provider-specific error mapping into shared LLM exceptions

### Cerebras adapter

Add a direct HTTP client with the same interface as OpenRouter:

- same return type
- same exception taxonomy
- same telemetry hooks

The transport interface should hide provider-specific details from agents.

## Service Refactor

Refactor [`src/cc_deep_research/agents/ai_analysis_service.py`](../src/cc_deep_research/agents/ai_analysis_service.py) so it no longer owns Claude-specific client initialization.

Target state:

- prompt builders and response parsers stay in analysis-focused code
- transport choice moves into the LLM routing layer
- `AIAnalysisService` asks for an operation like `extract_themes` or `synthesize_findings`
- the router chooses Claude CLI, OpenRouter, Cerebras, or heuristic fallback

Recommended first migration targets:

- [`src/cc_deep_research/agents/analyzer.py`](../src/cc_deep_research/agents/analyzer.py)
- [`src/cc_deep_research/agents/deep_analyzer.py`](../src/cc_deep_research/agents/deep_analyzer.py)
- [`src/cc_deep_research/agents/report_quality_evaluator.py`](../src/cc_deep_research/agents/report_quality_evaluator.py)

## Config Changes

Extend [`src/cc_deep_research/config.py`](../src/cc_deep_research/config.py) with a new `LLMConfig` tree instead of reusing `research.ai_integration_method` as the only switch.

Recommended shape:

- `llm.enabled_providers`
- `llm.default_fallback_order`
- `llm.claude_cli.path`
- `llm.claude_cli.timeout_seconds`
- `llm.openrouter.api_key`
- `llm.openrouter.base_url`
- `llm.openrouter.default_model`
- `llm.cerebras.api_key`
- `llm.cerebras.base_url`
- `llm.cerebras.default_model`
- `llm.agent_defaults.<agent>.preferred_provider`
- `llm.agent_defaults.<agent>.fallback_order`

Keep `research.ai_integration_method` during migration as a compatibility layer, then deprecate it after the new routing path is stable.

## Telemetry And Session Visibility

Extend [`src/cc_deep_research/monitoring.py`](../src/cc_deep_research/monitoring.py) so LLM telemetry is provider-neutral.

New event families:

- `llm.route.selected`
- `llm.route.fallback`
- `llm.request.started`
- `llm.request.completed`
- `llm.request.failed`

Common metadata fields:

- `agent_id`
- `operation`
- `transport`
- `provider`
- `model`
- `fallback_from`
- `fallback_reason`

Claude CLI subprocess events should remain, but hang under the generic request event so the dashboard can show API and CLI activity side by side.

## Delivery Phases

### Phase 1: LLM foundation

- add LLM config and models
- add route registry
- extract Claude CLI transport adapter
- add OpenRouter and Cerebras API adapters

### Phase 2: Planner-owned route plan

- extend strategy output with `llm_plan`
- resolve provider availability during planning
- persist route plan in session metadata

### Phase 3: Analyzer path migration

- route `AnalyzerAgent` and `DeepAnalyzerAgent` through the new LLM layer
- preserve heuristic fallback behavior
- prove mixed-route execution in one session

### Phase 4: Secondary agent migration

- migrate `ReportQualityEvaluatorAgent`
- optionally migrate `QueryExpanderAgent` and future LLM-backed validation helpers

### Phase 5: Cleanup and deprecation

- retire Claude-specific assumptions in shared services
- deprecate `research.ai_integration_method`
- update docs and CLI output

## Target Files

- [`src/cc_deep_research/config.py`](../src/cc_deep_research/config.py)
- [`src/cc_deep_research/models.py`](../src/cc_deep_research/models.py)
- [`src/cc_deep_research/orchestrator.py`](../src/cc_deep_research/orchestrator.py)
- [`src/cc_deep_research/orchestration/runtime.py`](../src/cc_deep_research/orchestration/runtime.py)
- [`src/cc_deep_research/orchestration/planning.py`](../src/cc_deep_research/orchestration/planning.py)
- [`src/cc_deep_research/orchestration/session_state.py`](../src/cc_deep_research/orchestration/session_state.py)
- [`src/cc_deep_research/agents/research_lead.py`](../src/cc_deep_research/agents/research_lead.py)
- [`src/cc_deep_research/agents/ai_analysis_service.py`](../src/cc_deep_research/agents/ai_analysis_service.py)
- [`src/cc_deep_research/agents/llm_analysis_client.py`](../src/cc_deep_research/agents/llm_analysis_client.py)
- [`src/cc_deep_research/agents/analyzer.py`](../src/cc_deep_research/agents/analyzer.py)
- [`src/cc_deep_research/agents/deep_analyzer.py`](../src/cc_deep_research/agents/deep_analyzer.py)
- [`src/cc_deep_research/agents/report_quality_evaluator.py`](../src/cc_deep_research/agents/report_quality_evaluator.py)
- [`src/cc_deep_research/monitoring.py`](../src/cc_deep_research/monitoring.py)
- [`tests/test_config.py`](../tests/test_config.py)
- [`tests/test_llm_analysis_client.py`](../tests/test_llm_analysis_client.py)
- new tests for routing, API adapters, and session metadata

## Acceptance Criteria

- one session can use mixed routes across agents
- planner output contains a per-agent LLM plan
- agents resolve routes at execution time, not constructor time
- Claude CLI, OpenRouter, and Cerebras share one transport contract
- route failures degrade to configured fallbacks without collapsing the run
- telemetry shows planned route, actual route, and fallback transitions
- persisted session metadata exposes route decisions and degradations

## Suggested Verification

Run a focused test pack after implementation:

```bash
uv run pytest \
  tests/test_config.py \
  tests/test_llm_analysis_client.py \
  tests/test_monitoring.py \
  tests/test_orchestrator.py \
  tests/test_telemetry.py
```

Add new tests for:

- route registry updates after planning
- planner selection when Claude CLI is unavailable
- mixed session execution where analyzer uses CLI and validator uses API
- OpenRouter and Cerebras adapter failures and fallback behavior
