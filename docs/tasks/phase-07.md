# Phase 07 - Research Workflow Upgrade

## Functional Feature Outcome

Research runs gain a reliable upgraded workflow surface: staged remains the production-safe default, planner becomes a contract-compatible beta path, and operators can choose, observe, benchmark, and compare workflows without breaking saved-session or dashboard contracts.

## Why This Phase Exists

The research runtime has two execution paths: the staged workflow is stable and deeply integrated with session metadata, telemetry, validation, reporting, and the dashboard, while the planner workflow is selectable but still thinner in metadata, observability, and operator exposure. This phase upgrades the workflow layer without replacing the working pipeline. It first makes both workflows honor the same persisted contract, then exposes workflow choices safely, improves retrieval and evidence quality, implements or hides unfinished replay affordances, and adds benchmark gates so future changes are measured instead of judged by ad hoc runs.

## Scope

- Unify staged and planner workflow outputs behind the same `ResearchSession.metadata` contract.
- Bring planner workflow telemetry, cancellation, provider metadata, prompt metadata, and degradation reporting to the same standard as staged runs.
- Expose workflow selection and execution controls in the dashboard with backend-compatible request fields.
- Improve retrieval quality through provider clarity, source ranking, content hydration fallback, and provenance-aware evidence handling.
- Tighten report validation and refinement so final reports do not contain placeholder TODOs or unsupported claims.
- Implement replay for checkpointed phase reruns, or remove/hide replay actions until real execution exists.
- Extend benchmark and regression gates so workflow upgrades can be compared across staged and planner runs.

## Tasks

| Task | Summary |
| --- | --- |
| [P7-T1](../tasks/phase-07/p7-t1-unify-research-session-contract.md) | Make staged and planner runs emit the same persisted metadata contract and add contract tests for both workflow modes. |
| [P7-T2](../tasks/phase-07/p7-t2-promote-planner-workflow-beta.md) | Upgrade planner execution to beta quality with cancellation, telemetry, prompt routing, provider metadata, degraded states, and explicit iteration semantics. |
| [P7-T3](../tasks/phase-07/p7-t3-expose-workflow-controls-dashboard.md) | Add dashboard controls for workflow, concurrency, provider selection, and backend-aligned request fields. |
| [P7-T4](../tasks/phase-07/p7-t4-upgrade-retrieval-quality.md) | Improve search provider clarity, source ranking, content hydration fallback, and retrieval provenance. |
| [P7-T5](../tasks/phase-07/p7-t5-tighten-evidence-and-report-quality.md) | Make claim evidence and report quality loops strict enough to prevent unsupported claims and placeholder refinement output. |
| [P7-T6](../tasks/phase-07/p7-t6-implement-or-hide-step-replay.md) | Implement replayable checkpoint reruns or remove replay affordances from operator surfaces until execution exists. |
| [P7-T7](../tasks/phase-07/p7-t7-add-workflow-benchmark-gates.md) | Extend the benchmark corpus and regression checks to compare staged and planner workflow behavior. |

## Dependencies

- Phase 01-06 refactors should remain intact: pipeline boundaries, route splits, model fixtures, dashboard state split, and existing strict mypy overrides are the safety baseline.
- `TeamResearchOrchestrator` must remain the default path until planner benchmark results are acceptable.
- Existing saved sessions and telemetry records must continue to load through compatibility normalizers.
- Dashboard API clients must remain compatible with existing backend route paths.
- Live provider-dependent verification requires configured search credentials, usually `TAVILY_API_KEYS`.
- LLM-backed quality checks require configured LLM routes, but heuristic fallbacks must still pass the offline test suite.

## Exit Criteria

- `ResearchRunRequest.workflow="staged"` and `"planner"` both produce sessions with the same top-level metadata keys: `strategy`, `analysis`, `validation`, `iteration_history`, `providers`, `execution`, `deep_analysis`, `llm_routes`, and `prompts`.
- Dashboard launch can select staged or planner workflow and sends backend field names exactly as defined by `ResearchRunRequest`.
- Planner runs emit monitor/session lifecycle events, final status, provider metadata, prompt metadata, route metadata, and explicit degraded/not-supported states.
- Retrieval reports expose source provenance, source type, freshness where available, and content hydration status.
- Report generation never adds TODO comments or placeholder sections during refinement.
- Replayable checkpoint UI/API behavior is honest: either reruns work, or the UI/API clearly hides or rejects unsupported replay without implying success.
- Benchmark output can compare staged and planner runs across source count, domain diversity, iteration count, validation score, stop reason, latency, and report quality.
- Required backend, dashboard, and benchmark regression checks are documented and pass before this phase is marked complete.
