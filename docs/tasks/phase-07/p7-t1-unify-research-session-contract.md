# P7-T1 - Unify Research Session Contract

## Functional Feature Outcome

Every research workflow returns a saved session that the dashboard, report generator, telemetry readers, and benchmark harness can consume through one stable contract.

## Why This Task Exists

The staged workflow already builds rich session metadata through `OrchestratorSessionState` and `SessionBuilder`. The planner workflow is selectable through `ResearchRunRequest.workflow`, but it currently builds a thinner metadata dictionary with planner-specific keys only. That creates two subtly different products under one API. Any workflow upgrade will become harder if downstream consumers need special cases for staged versus planner sessions.

## Scope

- Treat `ResearchSession.metadata` as the public workflow API.
- Make planner runs emit the same top-level metadata keys as staged runs.
- Preserve planner-specific details without replacing the common contract.
- Add regression tests that validate the metadata contract for both workflows.
- Keep compatibility for older saved sessions through existing session normalizers.

## Current Friction

- `ResearchRunRequest.workflow` already exposes `staged` and `planner`.
- `ResearchRunService.run_prepared()` switches to `PlannerResearchOrchestrator` when workflow is `planner`.
- `PlannerResearchOrchestrator._build_session()` currently builds a metadata object with keys such as `workflow`, `plan_id`, `plan_summary`, and `planner_confidence`, but not the full staged metadata contract.
- Dashboard and report code increasingly assume canonical metadata keys exist.

## Implementation Notes

- Add a shared metadata-building path for planner runs instead of duplicating ad hoc fields.
- Prefer reusing `SessionBuilder` and `OrchestratorSessionState` where practical.
- If planner cannot populate a contract area fully, populate an explicit empty/degraded state:
  - `validation`: `{}` only if validation truly did not run.
  - `iteration_history`: `[]` if planner does not run iterative follow-up.
  - `providers.status`: `ready`, `degraded`, or `unavailable`.
  - `execution.degraded`: `true` when planner skips a capability the operator requested.
  - `deep_analysis.status`: `not_requested`, `completed`, or `degraded`.
  - `llm_routes`: include planned/actual/usage/fallback fields even if empty.
  - `prompts`: include defaults and overrides metadata even if no overrides exist.
- Store planner-specific details under a nested key such as:

```python
metadata["planner"] = {
    "workflow": "planner",
    "plan_id": plan.plan_id,
    "plan_summary": plan.summary,
    "total_subtasks": len(plan.subtasks),
    "completed_subtasks": synthesis.completed_subtasks,
    "failed_subtasks": synthesis.failed_subtasks,
    "complexity": planner_result.complexity_assessment,
    "estimated_time_minutes": planner_result.estimated_time_minutes,
    "planner_confidence": planner_result.confidence,
}
```

## Test Plan

- Add `tests/test_research_workflow_contract.py` or extend `tests/test_research_run_service.py`.
- Use fake or stubbed orchestrator dependencies so tests do not require live provider credentials.
- Assert top-level metadata keys for staged and planner sessions.
- Assert planner metadata is nested rather than replacing canonical keys.
- Assert old session payloads still deserialize through `ResearchSession` normalization.

## Acceptance Criteria

- Staged and planner sessions share the same top-level metadata shape.
- Planner-specific metadata remains available under a clearly named nested key.
- Report generation works against planner sessions without special-casing missing metadata keys.
- Dashboard session detail pages can render planner sessions without runtime errors.
- Tests fail if a future workflow omits the canonical metadata keys.

## Verification Commands

```bash
uv run pytest tests/test_research_run_service.py tests/test_models.py tests/test_session_store.py -x
uv run pytest tests/test_web_server_research_run_routes.py tests/test_web_server_session_routes.py -x
uv run mypy src/cc_deep_research/research_runs/ src/cc_deep_research/orchestration/
```

## Risks

- Over-normalizing planner output could hide meaningful planner-specific state. Keep common contract fields canonical, but preserve planner details under `metadata["planner"]`.
- Existing fixtures may need updates if they assert exact metadata payloads. Update only when the changed shape is intentional.
