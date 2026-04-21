# Content-Generation Backlog

This document explains the content-generation backlog as it is currently implemented in `cc-deep-research`: what it is for, how it is structured, how operators manage it, and why the data model is shaped the way it is.

## What The Backlog Is For

The backlog is the persistent idea inventory for the short-form content workflow.

Its job is to sit between theme-level ideation and downstream execution:

- capture candidate ideas generated from a theme or created manually
- preserve operator edits across reruns
- store scoring and recommendation metadata without losing the original idea record
- track operator-managed backlog state separately from system-managed production progress
- keep provenance so operators know where an idea came from and which pipeline touched it

In practice, the backlog is not just a scratchpad of titles. It is the durable editorial queue the rest of the content-generation system reads from and writes back to.

## Mental Model

One backlog item is a single content candidate with four layers of information:

1. Editorial definition
   The idea itself, its audience, the viewer problem, the hook, and the evidence.
2. Decision support
   Scores, recommendations, selection reasoning, and genericity or proof-gap notes.
3. Provenance
   Which theme or pipeline created the idea.
4. Workflow state
   The operator-facing backlog state and the system-facing production progress.

That separation matters. A model recommendation like `produce_now` is not the same thing as an operator or system state like `selected` or `in_production`. The backlog keeps both.

## Where It Lives

Backlog persistence is handled by [`BacklogStore`](../src/cc_deep_research/content_gen/storage/backlog_store.py), which stores YAML on disk.

Path resolution is:

1. explicit path passed to the store or service
2. `content_gen.backlog_path` in config
3. default path: `~/.config/cc-deep-research/backlog.yaml`

Relevant code:

- path resolution: [`src/cc_deep_research/content_gen/storage/_paths.py`](../src/cc_deep_research/content_gen/storage/_paths.py)
- store: [`src/cc_deep_research/content_gen/storage/backlog_store.py`](../src/cc_deep_research/content_gen/storage/backlog_store.py)
- config schema: [`src/cc_deep_research/config/schema.py`](../src/cc_deep_research/config/schema.py)

## File Structure

The persistent file is validated as a `BacklogOutput` model, but operationally the important durable content is the `items` list.

Top-level shape:

```yaml
items:
  - idea_id: a1b2c3d4
    category: evergreen
    idea: Why onboarding wins or loses in the first 60 seconds
    audience: seed-stage SaaS founders
    problem: Activation drops after signup because the product shows setup, not value
    source: build_backlog
    why_now: Teams are cutting paid acquisition and need better activation efficiency
    potential_hook: Your onboarding probably fails before users even touch the product
    content_type: explainer
    evidence: benchmark reports, product teardown patterns, internal examples
    risk_level: medium
    priority_score: 0.0
    status: selected
    latest_score: 31
    latest_recommendation: produce_now
    selection_reasoning: Strong proof surface and clear pain for the primary audience
    expertise_reason: Fits prior content and operator expertise
    genericity_risk: Could collapse into generic onboarding advice without sharper proof
    proof_gap_note: Needs one strong primary source before scripting
    source_theme: onboarding
    source_pipeline_id: pipe_12345678
    created_at: 2026-04-14T08:11:12.000000+00:00
    updated_at: 2026-04-14T08:15:02.000000+00:00
    last_scored_at: 2026-04-14T08:14:40.000000+00:00
```

The `BacklogOutput` model also includes:

- `rejected_count`
- `rejection_reasons`
- `is_degraded`
- `degradation_reason`

Those fields are stage-output metadata from backlog generation. They are not the main persistent operating surface, and most backlog service operations actively maintain only `items`.

## Backlog Item Structure

The canonical schema lives in [`BacklogItem`](../src/cc_deep_research/content_gen/models/).

### Editorial fields

These fields exist so an idea is usable downstream, not just interesting at headline level:

- `idea`: the actual content idea
- `category`: one of `trend-responsive`, `evergreen`, or `authority-building`
- `audience`: who the content is for
- `problem`: the audience problem the idea addresses
- `source`: where the idea came from
- `why_now`: why this idea is timely
- `potential_hook`: opening-line or hook direction
- `content_type`: format hint
- `evidence`: what supports the idea
- `risk_level`: `low`, `medium`, or `high`

### Decision-support fields

These fields help choose what to make next:

- `priority_score`: reserved operator/system priority number, default `0.0`
- `latest_score`: latest aggregate scoring result
- `latest_recommendation`: `produce_now`, `hold`, or `kill`
- `selection_reasoning`: why the current selected idea won
- `expertise_reason`: why the idea fits the creator or brand
- `genericity_risk`: how the idea could become interchangeable or clichéd
- `proof_gap_note`: what evidence is still missing

### Provenance fields

- `source_theme`: theme that originally produced the idea
- `source_pipeline_id`: pipeline that generated or advanced it

### Lifecycle fields

- `idea_id`: stable item identifier
- `status`: operator-facing backlog state
- `production_status`: system-facing production progress
- `created_at`
- `updated_at`
- `last_scored_at`

## Status Model

Backlog status values are:

- `captured`
- `backlog`
- `selected`
- `archived`

Production status values are:

- `idle`
- `in_production`
- `ready_to_publish`

### What each field means

- `captured`: a raw idea was captured, but it still needs editorial shaping
- `backlog`: the item exists and is available for future selection
- `selected`: the operator chose this as the active item to focus on
- `archived`: intentionally removed from active circulation without deleting the record
- `idle`: no pipeline progress is currently recorded on the item
- `in_production`: the pipeline has progressed through scripting for this idea
- `ready_to_publish`: the pipeline reached publish-queue output for this idea

### Important implementation details

- `select_item()` enforces one selected item at a time. Selecting one item clears any previous `selected` item back to `backlog`.
- `runner_up` is system-derived from scoring and active candidate lanes, but it is no longer stored as backlog item status.
- Pipeline stages update `production_status`, not the operator-facing backlog `status`.

The precedence rule is implemented in [`_merge_backlog_status`](../src/cc_deep_research/content_gen/backlog_service.py).

## How Items Enter The Backlog

There are four main entry paths.

### 1. Pipeline backlog generation

Stage `build_backlog` generates ideas for a theme and then persists them through `BacklogService.persist_generated()`.

That persistence step:

- merges generated items into the existing backlog
- keeps operator-managed metadata where possible
- stamps `source_theme`
- stamps `source_pipeline_id`
- sets timestamps

Relevant code:

- stage implementation: [`src/cc_deep_research/content_gen/stages/backlog.py`](../src/cc_deep_research/content_gen/stages/backlog.py)
- service logic: [`src/cc_deep_research/content_gen/backlog_service.py`](../src/cc_deep_research/content_gen/backlog_service.py)

### 2. CLI backlog build

`cc-deep-research content-gen backlog build --theme "..."`

This command now generates ideas and persists them into the managed backlog store. If `-o/--output` is provided, it also writes a JSON export of the stage result.

### 3. Manual creation

The dashboard and API can create a new item directly through `BacklogService.create_item()`.

Manual creation defaults the new item to:

- `status="backlog"`
- `risk_level="medium"`
- new timestamps

### 4. Chat-proposed operations

The backlog chat flow can propose `create_item` and `update_item` operations. The `respond` endpoint is advisory only; nothing is persisted until the proposed operations are sent to the `apply` endpoint.

## How Scoring Works With The Backlog

Scoring is a separate stage from ideation.

The scorer evaluates each idea on seven dimensions:

- `relevance`
- `novelty`
- `authority_fit`
- `production_ease`
- `evidence_strength`
- `hook_strength`
- `repurposing`

The maximum total is `35`. The default `produce_now` threshold is `25`, configured via `content_gen.scoring_threshold_produce`.

When scoring is applied back to the persistent backlog, the service updates:

- `latest_score`
- `latest_recommendation`
- `last_scored_at`
- `selection_reasoning`
- `status` for `selected` and `runner_up` lanes

The output also builds a small active queue:

- one `primary` candidate
- zero or more `runner_up` candidates

That queue exists so the system can remember the current winner and one plausible alternate without treating the entire backlog as live execution context.

## How Users Manage The Backlog

There are three operator surfaces: CLI, dashboard/API, and chat-assisted editing.

### CLI

The CLI is generation- and scoring-oriented:

```bash
cc-deep-research content-gen backlog build --theme "pricing psychology" --count 20
cc-deep-research content-gen backlog score --from-file backlog.json --select-top 5
```

Important CLI behavior:

- `backlog build` persists generated items into the managed backlog file
- `backlog score` does not read the persistent backlog automatically
- `backlog score` expects explicit items, typically from `--from-file`
- before scoring, the CLI upserts those items into the backlog store
- after scoring, the CLI applies score metadata back onto the persistent backlog

So the CLI is good for structured generation and ranking, but not for general CRUD management.

### Dashboard and API

The dashboard backlog views are backed by these API routes in [`src/cc_deep_research/content_gen/router.py`](../src/cc_deep_research/content_gen/router.py):

- `POST /api/content-gen/backlog`
- `GET /api/content-gen/backlog`
- `PATCH /api/content-gen/backlog/{idea_id}`
- `POST /api/content-gen/backlog/{idea_id}/select`
- `POST /api/content-gen/backlog/{idea_id}/archive`
- `DELETE /api/content-gen/backlog/{idea_id}`
- `POST /api/content-gen/backlog/{idea_id}/start`

Operator actions supported by the dashboard/store layer include:

- load backlog
- filter by status and category
- create item
- edit item
- select item
- archive item
- delete item
- navigate to a detail page for a single item
- start a downstream pipeline run from one existing item

Two details matter here:

- the shared create/edit form only exposes a subset of fields: `idea`, `category`, `audience`, `problem`, `source_theme`, and `selection_reasoning`
- deeper fields like `why_now`, `potential_hook`, `evidence`, and `proof_gap_note` exist in the model and detail page, but are not fully editable through the lightweight dashboard form

### Chat-assisted editing

Backlog chat is intentionally two-step:

1. `respond` proposes operations and explains them
2. `apply` validates and persists those operations

This design keeps conversational editing useful without letting an LLM mutate the backlog as a side effect of every message.

## Starting A Pipeline From A Backlog Item

The backlog is also an execution handoff point.

`POST /api/content-gen/backlog/{idea_id}/start` creates a new pipeline run seeded from one existing backlog item.

The seeded context:

- uses that single item as the effective backlog
- marks it as the selected primary lane
- skips upstream ideation and scoring
- starts the pipeline at `generate_angles`

This matters because once an operator has chosen an item, re-running backlog generation or full rescoring would be redundant and potentially destructive.

The seeded-context helper is [`_build_seeded_context_from_backlog_item`](../src/cc_deep_research/content_gen/router.py).

## Theory Behind The Structure

The structure is opinionated. It is designed around four practical constraints.

### 1. Good ideas need more than titles

A backlog entry includes `audience`, `problem`, `why_now`, `potential_hook`, and `evidence` because the system is not trying to save a brainstorming wall. It is trying to save production-ready ideas.

Without those fields, later stages would have to rediscover the framing from scratch, which makes outputs more generic and less reliable.

### 2. Recommendation and commitment are different

`latest_recommendation` is the scorer's judgment.

`status` is the operating state of the item.

That split is deliberate. A model can recommend `hold` while an operator still keeps the item in `backlog`, or an item can stay `in_production` even after later scoring would have ranked it lower.

### 3. Provenance matters in editorial systems

`source_theme` and `source_pipeline_id` keep ideas attached to the context that created them. This helps answer:

- why does this idea exist?
- which theme or run produced it?
- which pipeline advanced it?

Without provenance, a backlog becomes an unstructured list of disconnected notes.

### 4. Progress should be monotonic

Once real downstream work happens, later ideation logic should not casually undo it.

That is why status merging protects:

- `in_production`
- `published`
- `archived`

from being demoted by a later scoring pass.

## Lifecycle In The Full Pipeline

The normal pipeline interaction looks like this:

```text
theme
  -> opportunity brief
  -> backlog generation
  -> backlog persisted
  -> scoring
  -> selected + runner-up lanes
  -> angle generation
  -> research pack
  -> argument map
  -> scripting
  -> backlog item marked in_production
  -> packaging / publish queue
  -> backlog item marked published
```

Two implementation nuances are worth calling out:

- `in_production` is currently set when scripting finishes, not when filming or editing begins in the real world
- `published` is currently set when publish-queue items are generated, not when an external platform confirms publication

So backlog status is pipeline-state truth, not guaranteed external platform truth.

## Caveats And Limits

- The backlog store is a single YAML file. There is no multi-writer locking or database-level concurrency model.
- The persistent schema is validated with Pydantic, so invalid manual edits can fail load/update operations.
- The dashboard form only edits a subset of the full model.
- `runner_up` exists in the backend data model but is not part of the shared manual status dropdown.
- `backlog score` is still file-oriented and does not score the managed backlog directly without an explicit input file.
- Stage-output metadata like `rejected_count` is useful at generation time, but the persistent operating model is item-centric.

## Key Source Files

- models: [`src/cc_deep_research/content_gen/models/`](../src/cc_deep_research/content_gen/models/)
- service: [`src/cc_deep_research/content_gen/backlog_service.py`](../src/cc_deep_research/content_gen/backlog_service.py)
- store: [`src/cc_deep_research/content_gen/storage/backlog_store.py`](../src/cc_deep_research/content_gen/storage/backlog_store.py)
- prompt contract: [`src/cc_deep_research/content_gen/prompts/backlog.py`](../src/cc_deep_research/content_gen/prompts/backlog.py)
- agent/parser: [`src/cc_deep_research/content_gen/agents/backlog.py`](../src/cc_deep_research/content_gen/agents/backlog.py)
- API routes: [`src/cc_deep_research/content_gen/router.py`](../src/cc_deep_research/content_gen/router.py)
- orchestration hooks: [`src/cc_deep_research/content_gen/pipeline.py`](../src/cc_deep_research/content_gen/pipeline.py)
- dashboard state: [`dashboard/src/hooks/useContentGen.ts`](../dashboard/src/hooks/useContentGen.ts)
- dashboard views: [`dashboard/src/components/content-gen/backlog-panel.tsx`](../dashboard/src/components/content-gen/backlog-panel.tsx) and [`dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx`](../dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx)

## Recommended Reading Order

If you are new to the feature, read in this order:

1. this document
2. [`content-generation.md`](content-generation.md) for the full workflow
3. [`src/cc_deep_research/content_gen/models/`](../src/cc_deep_research/content_gen/models/) for the canonical schema
4. [`src/cc_deep_research/content_gen/backlog_service.py`](../src/cc_deep_research/content_gen/backlog_service.py) for lifecycle rules
5. [`src/cc_deep_research/content_gen/router.py`](../src/cc_deep_research/content_gen/router.py) if you need the API contract
