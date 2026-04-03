# Task 01: Add Opportunity Brief Stage (Implemented)

## Status

Current status: Implemented

Evidence in the current codebase:

- `OpportunityBrief` exists in `src/cc_deep_research/content_gen/models.py`.
- `PipelineContext` stores `opportunity_brief`, and `PIPELINE_STAGES` includes `plan_opportunity`.
- `OpportunityPlanningAgent` and `prompts/opportunity.py` are implemented.
- The orchestrator runs `plan_opportunity` between strategy load and backlog generation.
- `docs/content-generation.md` reflects the updated stage order.
- `tests/test_content_gen.py` covers round-trip serialization, stage ordering, handler wiring, and blank-strategy execution.

## Goal

Add a new planning stage that turns raw theme input into a structured artifact before backlog generation.

## Why

The current pipeline starts with:

- load strategy
- build backlog from `theme + strategy`

That is too shallow. We need an explicit planning contract that can guide ideation and later scoring.

## Scope

In scope:

- add `OpportunityBrief` model
- add new pipeline stage name and label
- add `OpportunityPlanningAgent`
- add prompt module for the new stage
- store the result in `PipelineContext`
- update docs to reflect the new stage order

Out of scope:

- dashboard UI changes
- shortlist selection changes
- full telemetry wiring

## Suggested File Targets

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/agents/`
- `src/cc_deep_research/content_gen/prompts/`
- `docs/content-generation.md`

## Proposed Model

Suggested fields:

- `theme`
- `goal`
- `primary_audience_segment`
- `secondary_audience_segments`
- `problem_statements`
- `content_objective`
- `proof_requirements`
- `platform_constraints`
- `risk_constraints`
- `freshness_rationale`
- `sub_angles`
- `research_hypotheses`
- `success_criteria`

## Acceptance Criteria

- pipeline includes a `plan_opportunity` stage
- `PipelineContext` can store the planning artifact
- the stage runs after strategy load and before backlog generation
- backlog stage can read the new artifact, even if it does not fully use every field yet
- docs reflect the new stage order

## Testing

Add tests for:

- model round-trip serialization
- pipeline stage list and labels
- orchestrator writes `OpportunityBrief` into context
- stage can run with blank or minimal strategy memory

## Notes For Small Agent

Keep the first version narrow. Do not redesign backlog scoring in this task.
