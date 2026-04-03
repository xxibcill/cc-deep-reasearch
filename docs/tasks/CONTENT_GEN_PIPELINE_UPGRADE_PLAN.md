# Content Generation Pipeline Upgrade Plan (Partially Implemented)

## Status

Current status: Partially implemented

Task status snapshot:

- Task 01 `content-gen-01-opportunity-brief.md`: Implemented
- Task 02 `content-gen-02-stage-tracing.md`: Partially implemented
- Task 03 `content-gen-03-live-events.md`: Partially implemented
- Task 04 `content-gen-04-backlog-hardening.md`: Partially implemented
- Task 05 `content-gen-05-shortlist-selection.md`: Not implemented
- Task 06 `content-gen-06-dashboard-observability.md`: Not implemented
- Task 07 `content-gen-07-tests-and-fixtures.md`: Partially implemented

This roadmap is no longer fully future-tense. The planning stage, trace model, and several regression tests already exist, but shortlist selection, richer dashboard observability, and full live-event/test coverage are still incomplete.

This document turns the current content-generation pipeline into a concrete upgrade roadmap.

It is based on the current implementation in:

- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/agents/`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/router.py`
- `docs/content-generation.md`

## Objective

Improve the content-generation pipeline in three ways:

- make the first planning step smarter and more useful
- make pipeline execution easier to inspect and monitor in real time
- make ideation and selection more robust, explainable, and testable

## Why This Needs Work

The current pipeline shape is workable, but still narrow:

- strategy load is a passive memory fetch, not a planning step
- backlog generation is driven mostly by `theme + shallow strategy memory`
- idea selection is single-lane and picks the first `produce_now` item
- pipeline progress events are coarse and not rich enough for real monitoring
- scripting has step-level traces, but earlier content-gen stages do not
- content-gen agents already use `LLMRouter`, but pipeline-level telemetry is not wired through consistently

## Target State

The upgraded pipeline should:

1. turn a raw theme into a structured planning artifact before backlog generation
2. preserve stage-by-stage traces inside `PipelineContext`
3. emit true live progress and stage-completion signals
4. expose selection rationale, rejection reasons, parse health, and token/latency summaries
5. support shortlist-based decision-making rather than a first-hit winner

## Proposed Architecture Changes

## 1. Add an Opportunity Planning Stage

Insert a new stage after strategy load and before backlog generation:

- `plan_opportunity`

This stage should convert raw input into a structured `OpportunityBrief`.

Suggested output fields:

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

This becomes the planning contract for backlog generation and later scoring.

## 2. Deepen Ideation Outputs

Backlog generation should consume `OpportunityBrief`, not only raw theme text.

Backlog items should remain compact, but generation should be guided by:

- explicit audience
- explicit outcome
- explicit proof requirements
- explicit constraints
- explicit why-now framing

## 3. Add Pipeline Stage Tracing

Introduce structured traces for every pipeline stage, similar in spirit to scripting step traces.

Each trace should capture:

- stage name
- start and end timestamps
- duration
- input summary
- output summary
- warnings
- errors
- selection decisions
- LLM token and latency aggregates when available

## 4. Upgrade Monitoring and Live Events

The API should emit real stage lifecycle events:

- stage started
- stage completed
- stage failed
- stage skipped
- decision recorded

This should happen as stages complete, not in a post-run batch.

## 5. Replace First-Winner Selection With Shortlist Logic

Instead of:

- score ideas
- take the first `produce_now`

The pipeline should:

- build a ranked shortlist
- attach rationale for rank order
- record why the chosen idea won
- preserve alternates for operator review and future reuse

## 6. Harden Non-Scripting Stages

Earlier content-gen stages should fail loudly or mark degraded states when outputs are empty or malformed.

At minimum:

- backlog build
- scoring
- angle generation
- research-pack synthesis

should stop silently returning sparse results when parsing fails.

## Delivery Phases

## Phase 1: Planning Contract

Deliver:

- `OpportunityBrief` model
- new `plan_opportunity` stage
- prompt and agent for opportunity planning
- docs update for pipeline shape

## Phase 2: Traceability

Deliver:

- `PipelineStageTrace` model
- stage trace persistence in `PipelineContext`
- live stage completion events
- stage warnings and decision payloads

## Phase 3: Ideation Hardening

Deliver:

- backlog consumes `OpportunityBrief`
- stricter parsing and validation
- explicit degraded/error states

## Phase 4: Selection Upgrade

Deliver:

- shortlist-based scoring output
- chosen-idea rationale
- alternates retained in pipeline context

## Phase 5: Dashboard and Operator Visibility

Deliver:

- richer pipeline detail view
- trace summaries
- decision history
- stage metrics

## Phase 6: Evaluation and Regression Coverage

Deliver:

- fixture-backed tests for new pipeline behavior
- telemetry tests
- selection behavior tests
- malformed-output handling tests

## Suggested Task Breakdown

The work is intentionally split into small tasks under `docs/tasks/`.

Recommended execution order:

1. `content-gen-01-opportunity-brief.md`
2. `content-gen-02-stage-tracing.md`
3. `content-gen-03-live-events.md`
4. `content-gen-04-backlog-hardening.md`
5. `content-gen-05-shortlist-selection.md`
6. `content-gen-06-dashboard-observability.md`
7. `content-gen-07-tests-and-fixtures.md`

## Success Metrics

- the first planning step produces a structured brief, not only a loaded strategy blob
- backlog quality is easier to explain from saved context alone
- operators can tell what the pipeline is doing while it is running
- each stage exposes enough context to debug degraded or blank outputs
- idea selection is explainable and reversible
- tests cover the new contracts well enough to refactor safely
