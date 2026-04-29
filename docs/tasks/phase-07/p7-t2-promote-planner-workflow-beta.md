# P7-T2 - Promote Planner Workflow To Beta

## Functional Feature Outcome

Operators can run the planner workflow as an opt-in beta path with honest telemetry, cancellation, provider status, prompt routing, and execution semantics.

## Why This Task Exists

The planner workflow is conceptually useful for complex research because it decomposes a query into subtasks and executes independent work in groups. Today it is behind the same backend request contract as the staged workflow, but it does not yet match staged behavior for lifecycle telemetry, prompt configuration, provider metadata, degradation reporting, and iteration semantics. Promoting it to beta means making the path operationally understandable, not making it the default.

## Scope

- Keep staged as the default workflow.
- Add planner workflow lifecycle events that match the staged run lifecycle.
- Wire cancellation checks before and during major planner phases.
- Carry prompt registry and prompt override metadata into planner runs.
- Record provider resolution warnings and provider status for planner source collection.
- Decide and encode planner iteration semantics explicitly.
- Add planner-specific tests around task dispatch, partial failure, cancellation, and metadata.

## Current Friction

- Planner initialization creates local agents directly inside `PlannerResearchOrchestrator`.
- Planner execution does not use the same phase runner/checkpoint conventions as staged execution.
- Provider availability and degradation are implicit.
- Prompt overrides are applied to staged orchestrator construction but not planner construction.
- Iterative follow-up behavior is not equivalent to staged `AnalysisWorkflow`.

## Implementation Notes

- Extend `PlannerResearchOrchestrator.__init__()` to accept:
  - `prompt_registry`
  - `workflow_config`
  - optional concurrency settings when relevant
  - an injected provider/session-state object if needed for tests
- Emit monitor checkpoints for:
  - session start
  - planning
  - agent initialization
  - execution group start/completion
  - synthesis
  - validation
  - session complete/interrupted
- Use `cancellation_check` before:
  - plan creation
  - agent initialization
  - every execution group
  - every subtask handler
  - synthesis/session build
- If planner does not run staged-style iterative search yet, record:

```python
metadata["planner"]["iteration_policy"] = {
    "mode": "single_plan",
    "iterative_search_supported": False,
    "reason": "Planner beta executes one planned task graph and does not yet schedule validation-driven follow-up loops.",
}
```

- If planner should reuse staged iteration, route synthesis output through `AnalysisWorkflow` and document that decision in tests.
- Record partial subtask failures without failing the whole run when non-critical subtasks fail.
- Use stable stop reasons so telemetry comparisons do not need workflow-specific mapping.

## Test Plan

- Planner run succeeds with fake source collector/analyzer/validator/reporter agents.
- Planner run cancellation marks monitor/session state as interrupted.
- Planner run with one failed non-critical task records degradation but still returns a session.
- Planner run with provider unavailability records `providers.status = "unavailable"` and a failed or degraded terminal state as appropriate.
- Planner prompt overrides appear in `metadata["prompts"]`.
- Planner route metadata appears in `metadata["llm_routes"]`.

## Acceptance Criteria

- Planner can be launched through `ResearchRunService` with the same public request contract as staged.
- Planner emits enough telemetry for the existing monitor page and telemetry tree to explain what happened.
- Cancellation during planner execution produces an interrupted run, not an orphaned task.
- Provider and execution degradations are explicit in metadata.
- Planner remains opt-in until P7-T7 benchmark gates show acceptable performance.

## Verification Commands

```bash
uv run pytest tests/test_research_run_service.py tests/test_orchestration.py tests/test_monitoring.py -x
uv run pytest tests/test_web_server_research_run_routes.py tests/test_telemetry.py -x
uv run mypy src/cc_deep_research/orchestration/ src/cc_deep_research/research_runs/
```

## Risks

- Planner and staged workflows may drift if planner duplicates staged infrastructure. Prefer shared services for session, telemetry, source collection, and metadata.
- Planner may appear more capable than it is. Keep beta language and explicit metadata until benchmark data proves it can be promoted.
