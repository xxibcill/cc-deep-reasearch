# Task 016: Formalize Local Runtime Boundary

Status: Done

## Objective

Finish the remaining architecture-honesty cleanup by implementing the actual local runtime boundary in code.

Most of the naming and documentation cleanup has already landed:

- the real workflow is described as orchestrator-led and local
- local-only scaffolding now uses `LocalResearchTeam`, `LocalMessageBus`, and `LocalAgentPool`
- contributor docs already warn that parallel mode is local task fan-out, not distributed worker orchestration

The main gap left is that `runtime.py` is still empty even though the orchestrator now depends on `OrchestratorRuntime`.

## Problem Statement

The repo still mixes two different architecture stories:

1. the real one:
   - `TeamResearchOrchestrator` owns the workflow
   - specialist agents are local Python objects
   - parallel mode is local async task fan-out for source collection

2. the implied one:
   - a team object executes research
   - a message bus coordinates agents
   - an agent pool manages worker execution

That second story is not implemented as a real runtime.

Concrete symptoms:

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/runtime.py` is empty
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py` constructs `OrchestratorRuntime` and delegates lifecycle to it, but the runtime contract is not implemented
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/teams/research_team.py` still exposes `LocalResearchTeam.execute_research()` even though it only returns a placeholder session
- tests do not yet lock down the concrete runtime lifecycle or the placeholder-only team entrypoint

Impact:

- contributors can edit the wrong abstraction layer
- the runtime contract is harder to understand and test
- future refactors can accidentally deepen the mismatch
- "multi-agent" claims remain easy to over-interpret

## Already Implemented

- local-first names are already in place for team and coordination scaffolding
- `docs/RESEARCH_WORKFLOW.md`, `docs/RESEARCH_WORKFLOW_AGENT_INTERACTIONS.md`, and `docs/USAGE.md` already describe the runtime as orchestrator-led and local
- `TeamResearchOrchestrator` already routes startup and shutdown through `_runtime.initialize()` and `_runtime.shutdown()`

## Scope

- implement a real local `OrchestratorRuntime` instead of leaving the abstraction empty
- make the local runtime state and lifecycle typed and explicit
- remove or narrow placeholder execution surfaces that still look production-ready
- keep the current local orchestrator model as the source of truth
- update only the docs and tests that are still stale after the runtime implementation lands

Out of scope:

- building a real distributed multi-agent worker runtime
- introducing external worker processes
- message-driven phase execution
- redesigning the research workflow itself

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/runtime.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/teams/research_team.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestration/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW_AGENT_INTERACTIONS.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_teams.py`

## Dependencies

- [003_orchestrator_contract_tests.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/003_orchestrator_contract_tests.md)
- [011_architecture_honesty_cleanup.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/011_architecture_honesty_cleanup.md)

## Implementation Plan

### Phase 1: Implement the runtime module

- add a concrete `OrchestratorRuntime` implementation in `runtime.py`
- define a typed runtime-state model or dataclass for:
  - local team wrapper
  - agent mapping
  - optional local message bus
  - optional local agent pool
- move local runtime initialization details into that module
- ensure `initialize()` and `shutdown()` are the canonical lifecycle hooks used by the orchestrator

### Phase 2: Tighten the remaining placeholder surface

- review `LocalResearchTeam.execute_research()`
- either remove it from the active contract or replace the placeholder return with a hard failure such as `NotImplementedError`
- keep the team wrapper focused on metadata and lifecycle if the project is staying local-first

### Phase 3: Lock the boundary with tests and minimal doc updates

- add tests that verify orchestrator startup uses the concrete runtime module
- add tests that verify shutdown cleans up the local runtime state
- add tests that ensure placeholder team APIs are not mistaken for the real research path
- update only the docs that still describe `runtime.py` as empty or imply a broader runtime than the code actually provides

## Acceptance Criteria

- `runtime.py` contains the real local runtime implementation used by the orchestrator
- the orchestrator no longer depends on an implicit or missing runtime contract
- placeholder team execution methods do not look like valid workflow entrypoints
- docs and code describe the same runtime model
- tests protect the runtime boundary from regressing back into ambiguity

## Suggested Verification

- run `uv run pytest tests/test_orchestrator.py tests/test_teams.py`
- run `uv run ruff check src/cc_deep_research/orchestrator.py src/cc_deep_research/orchestration/runtime.py src/cc_deep_research/teams/research_team.py tests/test_orchestrator.py tests/test_teams.py`

## Notes For The Implementer

- Do not revisit naming-only cleanup unless the runtime implementation requires it.
- Do not over-engineer a distributed runtime in this task.
- The goal is to make the current local model explicit and honest.
- If a future real multi-agent runtime is desired, it should land as a separate task with explicit task envelopes, message protocol, worker lifecycle, retry semantics, and scheduling policy.
