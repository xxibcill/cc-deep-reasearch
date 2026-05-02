# Phase 15 - Research Execution Runtime Deepening

## Functional Feature Outcome

Research execution relies on clearer runtime boundaries so staged workflow changes can be tested through execution services instead of top-level orchestrator compatibility hooks.

## Why This Phase Exists

The research runtime has already been partially refactored into execution, planning, source collection, and analysis services, but the top-level orchestrator still provides compatibility methods and builds a callback bundle for execution. That keeps the runtime boundary shallow: execution services still depend on top-level hooks for important behavior. This phase deepens the research execution boundary after the higher-risk content-gen refactors, making staged workflow changes easier to verify and reducing facade behavior in `TeamResearchOrchestrator`.

## Scope

- Identify execution behavior still routed through top-level orchestrator compatibility hooks.
- Move runtime behavior into focused orchestration services where the boundary already exists.
- Preserve the public `TeamResearchOrchestrator` API.
- Add service-level tests for phase execution, source collection, analysis, and degraded behavior.

## Tasks

| Task | Summary |
| --- | --- |
| [P15-T1](../tasks/phase-15/p15-t1-deepen-research-execution-runtime.md) | Deepen research execution service boundaries and reduce top-level orchestrator compatibility behavior. |

## Dependencies

- Existing research workflow contract tests should stay green.
- Provider-dependent behavior must remain mockable for offline tests.
- Saved session metadata and dashboard session consumers must remain compatible.

## Exit Criteria

- Execution behavior is tested through orchestration services rather than only through the top-level orchestrator.
- The top-level orchestrator retains public compatibility but owns less execution detail.
- Source collection, analysis workflow, and execution degraded states have focused tests.
- Staged research runs preserve saved session and telemetry behavior.
