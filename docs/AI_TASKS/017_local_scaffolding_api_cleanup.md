# Task 017: Narrow The Local Scaffolding API Surface

Status: Planned

## Objective

Finish the next phase of the architecture-honesty work by reducing or deprecating
the remaining public APIs that still make the local runtime look like a broader
agent coordination system than it really is.

Task `016` made the orchestrator's local runtime boundary concrete and testable.
The next gap is no longer the hot path itself. It is the compatibility surface
around that hot path.

## Problem Statement

The codebase now correctly executes research through:

- `TeamResearchOrchestrator`
- `OrchestratorRuntime`
- local in-process specialist agents
- optional local async task fan-out for source collection

But several exported names and placeholder helper methods still imply a more
general team runtime than the code actually provides.

Concrete symptoms:

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/teams/research_team.py` still exports `ResearchTeam` as an alias of `LocalResearchTeam`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/agent_pool.py` still exports `AgentPool` as an alias of `LocalAgentPool`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/message_bus.py` still exports `MessageBus` as an alias of `LocalMessageBus`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/__init__.py` still re-exports `ResearchTeam` at the package root
- `LocalResearchTeam` still carries placeholder methods such as `spawn_researcher()` and `send_message()` that look operational even though the normal workflow does not use them
- contributor docs still need one more pass so the "Reality Check" examples match the implemented behavior, including the fact that `LocalResearchTeam.execute_research()` now raises `NotImplementedError`

Impact:

- contributors can still import and extend the wrong abstraction layer
- tests and examples can reinforce the wrong mental model
- future refactors may calcify compatibility aliases into pseudo-contracts
- the repo still advertises more coordination machinery than the real local runtime needs

## Scope

- make the local-only names the primary API surface
- remove, narrow, or explicitly deprecate compatibility aliases that imply a real team runtime
- review placeholder coordination helpers on `LocalResearchTeam` and keep only the surfaces that are still justified
- update docs and examples so they describe the implemented local pipeline without fallback to old alias names
- add tests that prevent the compatibility surface from drifting back into ambiguity

Out of scope:

- building a real distributed worker runtime
- introducing external agent processes
- redesigning the orchestrator workflow
- changing the retrieval, analysis, or validation logic

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/teams/research_team.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/teams/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/agent_pool.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/message_bus.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW_AGENT_INTERACTIONS.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_teams.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`

## Dependencies

- [011_architecture_honesty_cleanup.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/011_architecture_honesty_cleanup.md)
- [016_local_runtime_boundary_completion.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/016_local_runtime_boundary_completion.md)

## Implementation Plan

### Phase 1: Make the public names honest

- audit package exports in `teams`, `coordination`, and the package root
- decide which compatibility aliases should be removed versus kept with explicit deprecation warnings
- ensure the default documented imports use `LocalResearchTeam`, `LocalAgentPool`, and `LocalMessageBus` where those types still need to be public at all

### Phase 2: Quarantine placeholder coordination helpers

- review `LocalResearchTeam.spawn_researcher()`, `send_message()`, and `collect_results()`
- either remove those methods from the supported surface or rename/document them as experimental local scaffolding
- keep the team wrapper focused on lifecycle metadata that the orchestrator runtime actually needs

### Phase 3: Lock the boundary in docs and tests

- update the workflow docs so the "Reality Check" section matches current code
- remove examples that normalize `ResearchTeam`, `AgentPool`, or `MessageBus` as first-class runtime primitives unless they are explicitly marked as compatibility-only
- add tests that verify the supported import surface and guard against reintroducing misleading aliases without deliberate review

## Acceptance Criteria

- the codebase has one clear default story: orchestrator-led local runtime
- compatibility aliases that imply a real team runtime are either removed or clearly deprecated
- placeholder coordination helpers do not look like production workflow APIs
- docs no longer describe `LocalResearchTeam.execute_research()` as returning a placeholder session
- tests protect the narrowed public surface from regressing back into ambiguity

## Suggested Verification

- run `uv run pytest tests/test_teams.py tests/test_orchestrator.py`
- run `uv run ruff check src/cc_deep_research/teams/research_team.py src/cc_deep_research/teams/__init__.py src/cc_deep_research/coordination/agent_pool.py src/cc_deep_research/coordination/message_bus.py src/cc_deep_research/coordination/__init__.py src/cc_deep_research/__init__.py tests/test_teams.py tests/test_orchestrator.py`

## Notes For The Implementer

- Prefer the local-pipeline direction from the improvement plan rather than preserving broad compatibility names by default.
- If a compatibility alias must remain for import stability, make the deprecation explicit in code and docs.
- Do not add new coordination scaffolding in this task.
- The goal is to make the supported API as honest as the runtime implementation already is.
