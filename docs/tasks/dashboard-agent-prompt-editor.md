# Dashboard Agent Prompt Editor Tasks

Status: Done

## Goal

Allow operators to edit agent prompts for a research run from the dashboard, with the selected prompt configuration flowing through the backend into execution and session metadata.

## Scope

- Add per-run prompt override inputs to the dashboard
- Support prompt overrides for agents that currently use LLM prompts in the existing workflow
- Persist effective prompt configuration into session metadata for auditability
- Keep prompt handling centralized instead of scattering override logic across agents

## Non-Goals

- Live-editing prompts for in-flight runs
- Full prompt editing for heuristic-only agents in v1
- Building a permanent prompt-library management system in v1

## Current Constraint

Not every agent in this codebase has a real editable prompt today.

- `lead`, `expander`, and `validator` are primarily heuristic and do not currently expose true LLM prompt surfaces
- `analyzer`, `deep_analyzer`, and `report_quality_evaluator` are the most realistic v1 targets

To avoid a misleading UI, v1 should only expose prompt editing for agents that actually consume prompts during execution.

## Task Breakdown

### 1. Define the prompt override request contract

**Why**
The dashboard needs a stable payload for sending per-agent prompt overrides to the backend.

**Work**
- Add a typed prompt override structure to the shared research-run request model
- Mirror the contract in dashboard TypeScript types
- Normalize supported agent ids and reject unknown shapes

**Recommended contract**
- `agent_prompt_overrides: { [agentId]: { system_prompt?: string, prompt_prefix?: string } }`

**Acceptance criteria**
- Browser-started runs can include prompt overrides in the request payload
- Invalid override payloads fail validation cleanly
- The contract supports partial overrides per agent

**Likely files**
- `src/cc_deep_research/research_runs/models.py`
- `dashboard/src/types/telemetry.ts`

### 2. Propagate prompt overrides through research run preparation

**Why**
The request payload needs to survive the API and service layers before runtime agent construction begins.

**Work**
- Thread the prompt override payload through request preparation
- Store the resolved override data on the config or runtime input used by the orchestrator
- Avoid special-casing this inside the web route

**Acceptance criteria**
- Prompt overrides submitted from the dashboard are available when agents are instantiated
- CLI and dashboard execution paths remain consistent

**Likely files**
- `src/cc_deep_research/research_runs/service.py`
- `src/cc_deep_research/research_runs/options.py`
- `src/cc_deep_research/web_server.py`

### 3. Add a centralized prompt registry/resolver

**Why**
Prompt logic is currently spread across multiple agents. Override behavior needs one source of truth.

**Work**
- Add a backend prompt registry module
- Define default prompts or instruction blocks by agent and operation
- Add merge rules for default prompt plus override
- Validate prompt sizes and strip obviously empty overrides

**Recommended behavior**
- Prefer override-as-augmentation for v1, not blind full replacement
- Keep structured task prompts intact and let `system_prompt` or `prompt_prefix` change agent behavior safely

**Acceptance criteria**
- Agents resolve prompts through a shared helper instead of bespoke string merging
- Defaults still work when no override is provided
- Empty or whitespace-only overrides do not alter behavior

**Likely files**
- new: `src/cc_deep_research/prompts/registry.py`
- new: `src/cc_deep_research/prompts/__init__.py`

### 4. Wire prompt overrides into LLM-backed agents

**Why**
The backend needs actual execution points where prompt overrides take effect.

**Work**
- Update analysis prompt generation to read from the prompt registry
- Update report-quality evaluation prompt generation to read from the prompt registry
- Pass per-agent prompt configuration during runtime agent construction

**Primary v1 targets**
- `analyzer`
- `deep_analyzer`
- `report_quality_evaluator`

**Acceptance criteria**
- A dashboard-provided override changes the prompt used by supported agents
- Unsupported agents are ignored or rejected explicitly rather than failing silently

**Likely files**
- `src/cc_deep_research/orchestration/runtime.py`
- `src/cc_deep_research/agents/ai_analysis_service.py`
- `src/cc_deep_research/agents/llm_analysis_client.py`
- `src/cc_deep_research/agents/report_quality_evaluator.py`

### 5. Persist prompt configuration in session metadata

**Why**
Operators need to know which prompt settings were used for a finished run.

**Work**
- Save prompt overrides in normalized session metadata
- Save the effective agent prompt configuration used for the run
- Keep the metadata shape stable for future session inspection UI

**Suggested metadata keys**
- `prompt_overrides`
- `effective_agent_prompts`

**Acceptance criteria**
- A completed session contains the prompt configuration used for execution
- Session metadata remains backward-compatible for older sessions without prompt data

**Likely files**
- `src/cc_deep_research/models/session.py`
- `src/cc_deep_research/orchestrator.py`
- `src/cc_deep_research/orchestration/session_state.py`

### 6. Add dashboard form support for prompt editing

**Why**
The operator entry point for this feature is the dashboard run form.

**Work**
- Add an advanced section to the start research form
- Add one textarea per supported agent
- Show helper copy explaining which agents are editable in v1
- Add reset-to-default behavior for each editable prompt

**Acceptance criteria**
- Operators can submit a run with prompt overrides from the dashboard
- The form remains usable when no overrides are provided
- The UI makes the v1 support boundary clear

**Likely files**
- `dashboard/src/components/start-research-form.tsx`
- `dashboard/src/lib/api.ts`
- `dashboard/src/components/ui/*`

### 7. Expose configured prompts in the session UI

**Why**
The session view should show configured prompt inputs separately from runtime prompt previews in telemetry.

**Work**
- Add a lightweight panel for configured agent prompts or prompt overrides
- Keep this separate from the LLM reasoning list, which already shows prompt previews from telemetry

**Acceptance criteria**
- Operators can inspect the prompt configuration used for a session without reading raw JSON
- The existing LLM reasoning panel remains focused on runtime interactions

**Likely files**
- `dashboard/src/components/session-details.tsx`
- `dashboard/src/components/llm-reasoning-panel.tsx`
- `dashboard/src/app/session/[id]/page.tsx`

### 8. Add backend tests for prompt override flows

**Why**
This feature crosses request validation, orchestration, prompt construction, and persistence.

**Work**
- Test research-run request validation for prompt overrides
- Test prompt merge behavior
- Test supported and unsupported agent handling
- Test session metadata persistence
- Test API serialization for prompt config

**Acceptance criteria**
- Tests cover both the happy path and invalid input cases
- Prompt overrides do not regress default behavior when omitted

**Likely files**
- `tests/test_research_run_service.py`
- `tests/test_web_server.py`
- new: `tests/test_prompt_registry.py`

### 9. Add frontend tests for request-building and UI behavior

**Why**
The dashboard form needs coverage for advanced-field state and payload generation.

**Work**
- Test that prompt fields serialize into the research run request
- Test reset-to-default behavior
- Test validation or empty-state behavior for prompt inputs

**Acceptance criteria**
- The UI sends the expected payload for supported prompt overrides
- Empty inputs do not send meaningless override data

**Likely files**
- `dashboard/src/components/start-research-form.tsx`
- frontend test files if the repo already uses them for dashboard components

### 10. Plan v2 for heuristic-only agents

**Why**
If product requirements remain “edit prompt of each agent,” the remaining agents need to be converted from hard-coded heuristics into template-driven instruction systems.

**Work**
- Identify which heuristic agents should expose editable instruction templates
- Decide whether those templates are true prompts, system instructions, or configurable heuristics
- Introduce consistent prompt/template interfaces for `lead`, `expander`, and `validator`

**Acceptance criteria**
- The team has a clear follow-up path to support literal per-agent editing across the entire workflow
- The product does not overpromise v1 capabilities

**Likely files**
- `src/cc_deep_research/agents/research_lead.py`
- `src/cc_deep_research/agents/query_expander.py`
- `src/cc_deep_research/agents/validator.py`

## Recommended Delivery Phases

### Phase 1

- Add request contract
- Add prompt registry
- Support prompt overrides for LLM-backed agents
- Add dashboard form inputs
- Persist prompt config in session metadata

### Phase 2

- Refactor heuristic agents into template-driven instruction surfaces
- Expand dashboard editing to every agent only after those prompt surfaces are real

## Recommendation

Ship v1 as a scoped, honest feature: editable prompts for LLM-backed agents per run from the dashboard. Do not label heuristic agents as prompt-editable until the backend actually supports configurable instruction surfaces for them.
