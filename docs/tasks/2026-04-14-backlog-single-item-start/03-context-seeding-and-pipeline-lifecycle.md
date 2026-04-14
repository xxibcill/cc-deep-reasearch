# Task 03: Context Seeding And Pipeline Lifecycle

## Objective

Define the minimum valid `PipelineContext` and lifecycle expectations for starting the pipeline from one existing backlog item.

This document exists to prevent the implementation from over-seeding fake data or re-running unnecessary upstream stages.

## Core Principle

Seed only the data needed to satisfy the orchestrator at `generate_angles`.

Do not pretend the pipeline has already completed:

- scoring
- angle generation
- research pack
- argument map
- scripting

Those outputs should remain empty and be produced normally by downstream stages.

## Existing Orchestrator Behavior That Matters

### Candidate resolution

The orchestrator can derive a primary lane from:

- `selected_idea_id`
- `active_candidates`
- backlog items

If no explicit candidates exist, it can still derive a primary candidate from the selected idea. This means the seeded context does not need a full `ScoringOutput` to proceed.

### Stage prerequisites

For `generate_angles`, the orchestrator requires:

- `ctx.backlog` to exist
- at least one resolvable selected or active candidate whose `idea_id` maps to an item in the backlog

That is the crucial boundary that makes this feature feasible without re-running `score_ideas`.

### Status transition

At the end of scripting, the orchestrator already calls:

- `BacklogService.mark_in_production(candidate.idea_id, source_pipeline_id=ctx.pipeline_id)`

That means the start-from-backlog flow does not need to introduce its own early write to `in_production`.

## Recommended Seeded Context Shape

The initial context should include the following fields.

### Required identifiers

- `pipeline_id`
- `theme`
- `created_at`
- `current_stage`

Suggested values:

- `pipeline_id = job.pipeline_id`
- `theme = item.source_theme or item.idea`
- `created_at = now`
- `current_stage = 4`

### Strategy

Populate:

- `strategy`

Recommended source:

- existing strategy store

Reason:

- `generate_angles` and downstream stages use strategy context when present
- loading it up front keeps the new route behavior closer to normal pipeline execution

If no strategy exists, an empty/default strategy object is acceptable if that is already the repo norm.

### Backlog

Populate:

- `backlog = BacklogOutput(items=[item])`

Important:

- Use the real persisted backlog item
- Do not create a synthetic stripped-down item unless serialization forces it

The pipeline should be able to resolve the selected item directly from the seeded backlog snapshot.

### Selection fields

Populate:

- `selected_idea_id = item.idea_id`
- `shortlist = [item.idea_id]`
- `selection_reasoning`
- `runner_up_idea_ids = []`

Recommended `selection_reasoning`:

- preserve `item.selection_reasoning` if present
- otherwise use a deterministic operator-driven reason such as:
  - `"Started explicitly by operator from backlog."`

### Active candidates

Populate:

- `active_candidates = [PipelineCandidate(...)]`

Recommended candidate:

```python
PipelineCandidate(
    idea_id=item.idea_id,
    role="primary",
    status="selected",
)
```

This ensures lane derivation is explicit and does not depend on fallback behavior alone.

### Downstream fields that should remain empty

Leave unset or empty:

- `scoring`
- `angles`
- `research_pack`
- `argument_map`
- `scripting`
- `visual_plan`
- `production_brief`
- `packaging`
- `qc_gate`
- `publish_items`
- `publish_item`
- `performance`
- `iteration_state`
- `stage_traces`

These fields should be produced by the normal pipeline execution path.

## Why Not Seed `ScoringOutput`

It may be tempting to fabricate a `ScoringOutput` to make the context "look complete." Do not do that unless the orchestrator truly forces it.

Reasons to avoid fake scoring:

- it introduces invented shortlist and rationale data
- it increases maintenance burden if scoring models change
- it creates ambiguity about whether the operator or the model selected the item

The operator explicitly chose the item. That choice should be represented directly in the context rather than laundered through synthetic scoring output.

## Why Not Start At `score_ideas`

Starting at stage index `3` would re-enter model-driven idea scoring and selection.

Problems:

- it may choose a different item than the operator clicked
- it may rewrite backlog status semantics
- it turns a user-explicit action into a probabilistic selection flow

The product requirement here is "start this item," not "reconsider which item should start."

## Why Not Use Standalone Scripting

The standalone scripting route only accepts raw `idea` text and runs a separate scripting flow. It does not:

- create a pipeline job with pipeline detail visibility
- preserve downstream pipeline observability
- naturally produce the same context artifacts as the full production pipeline
- align with backlog-item-specific lineage

That route is useful for quick script generation, not for backlog-to-production lifecycle management.

## Pipeline Lifecycle Expectations

### At creation time

The run should appear as a normal queued/running pipeline job.

### During downstream execution

The pipeline should publish the same stage events as any other run:

- stage started
- stage completed
- stage failed
- pipeline completed

### After scripting

The backlog item should be marked `in_production` by existing logic.

### After terminal completion

The run should behave like any other pipeline run in:

- list views
- detail view
- WebSocket updates
- downstream publish and performance steps

## Duplicate Active Run Semantics

This document recommends a conservative default:

- one active pipeline per backlog item

Why:

- reduces operator confusion
- avoids duplicate writes to downstream artifacts
- makes backlog status easier to reason about

If a future product decision allows multiple concurrent runs per item, that should be designed deliberately rather than left as an accidental byproduct of missing guards.

## Suggested Helper Responsibilities

You will likely want one or two helpers with narrow responsibilities.

Recommended split:

- `load_backlog_item_for_start(...)`
- `build_seeded_single_item_context(...)`

Keep them deterministic and easy to unit test.

Avoid a helper that both loads data, creates jobs, starts tasks, and mutates backlog state. That shape becomes hard to test and harder to extend.

## Acceptance Criteria

- Seeded context passes orchestrator prerequisite validation for `generate_angles`.
- The primary candidate resolves to the requested backlog item.
- No fake downstream artifacts are prepopulated.
- Normal pipeline execution fills later stages.
- Existing `in_production` marking remains the source of truth.

## Advice For The Implementer

- Test the seeded context against the orchestrator’s prerequisite checks directly.
- Resist the urge to "complete" the context with guessed values.
- Treat `selected_idea_id`, backlog snapshot, and active candidates as the canonical minimal seed.
