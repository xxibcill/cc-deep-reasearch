# Decision Graph Emission Coverage Tasks

Status: Done

## Goal

Increase explicit decision telemetry coverage so the decision graph is useful in real sessions rather than sparse and mostly inferred.

## Scope

- Add `decision.made` events to major orchestration branches
- Reuse the existing `emit_decision_made()` helper
- Preserve current behavior while improving observability

## Non-Goals

- Refactoring every orchestration path in one pass
- Capturing full chain-of-thought or private model reasoning

## Task Breakdown

### 1. Cover LLM routing decisions

**Why**
Routing and fallback choices are already central to the runtime, and they are some of the most operator-relevant decisions.

**Work**
- Emit decisions when a route is selected
- Emit decisions when a fallback route is chosen
- Emit decisions when retries or degraded routes are accepted

**Suggested decision types**
- `routing`
- `fallback`
- `retry_route`

**Acceptance criteria**
- Route planner and runtime router emit explicit `decision.made` records
- Decision metadata includes chosen transport, rejected transports, and reason code

**Likely files**
- `src/cc_deep_research/llm/router.py`
- `src/cc_deep_research/orchestration/llm_route_planner.py`

### 2. Cover iteration control decisions

**Why**
Continue versus stop is one of the most important workflow decisions, and it should appear explicitly in the graph.

**Work**
- Emit explicit decisions for:
  - continue iteration
  - stop iteration
  - request follow-up queries
- Link them to relevant analysis or validation cause events when available

**Acceptance criteria**
- Follow-up and stop choices are visible as explicit decisions rather than only derived summaries
- The decision graph can show why a run stopped or continued

**Likely files**
- `src/cc_deep_research/orchestration/analysis_workflow.py`
- `src/cc_deep_research/orchestrator.py`

### 3. Cover provider and execution-state decisions

**Why**
State transitions are more useful when the operator can see the decision that caused them.

**Work**
- Emit decisions when:
  - provider availability changes cause a route change
  - degraded execution is accepted
  - a mitigation path is chosen
- Pair them with `state.changed` and `degradation.detected` where appropriate

**Acceptance criteria**
- Decision and state-change events can be linked directly in the graph
- Recovery and degraded-mode behavior are no longer mostly inferred

**Likely files**
- `src/cc_deep_research/orchestration/session_state.py`
- `src/cc_deep_research/agents/ai_analysis_service.py`
- `src/cc_deep_research/llm/router.py`

### 4. Cover planner decomposition decisions

**Why**
The planner is an obvious source of meaningful graph nodes, especially for complex research runs.

**Work**
- Emit decisions for:
  - decomposition strategy
  - major branch selection
  - route/default selection for agents
- Keep payloads concise and structured

**Acceptance criteria**
- Planner-originated choices appear as explicit decision nodes
- Operator can distinguish planner decisions from runtime recovery decisions

**Likely files**
- `src/cc_deep_research/agents/planner.py`
- `src/cc_deep_research/orchestration/planner_orchestrator.py`
- `src/cc_deep_research/orchestration/llm_route_planner.py`

### 5. Normalize decision payload conventions

**Why**
Graph quality will degrade quickly if different code paths use inconsistent metadata.

**Work**
- Standardize:
  - `decision_type`
  - `reason_code`
  - `chosen_option`
  - `rejected_options`
  - `inputs`
  - `cause_event_ids`
  - `confidence`
- Prefer enums or shared constants where practical

**Acceptance criteria**
- The same decision type means the same thing across routing, planning, and iteration flows
- UI code does not need per-source special cases for core fields

**Likely files**
- `src/cc_deep_research/monitoring.py`
- routing/planning/orchestration call sites

### 6. Add focused emission tests

**Why**
Coverage work will otherwise drift or silently regress.

**Work**
- Add tests for each major decision family:
  - routing
  - fallback
  - stop/continue
  - provider-state change
  - planner choice

**Acceptance criteria**
- Tests verify explicit `decision.made` events are emitted with useful metadata
- Emitted cause links reference real event IDs where available

**Likely files**
- `tests/test_monitoring.py`
- `tests/test_llm_route_planner.py`
- `tests/test_orchestrator.py`
- `tests/test_telemetry.py`
