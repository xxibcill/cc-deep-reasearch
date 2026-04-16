# Content Generation Pipeline Artifacts, Persistence, Dashboard Control, and Video Production Boundary

This document explains four things about the content-generation subsystem in this repository:

1. what artifacts the content-generation pipeline produces
2. what "persistence" means in this codebase
3. what operators can manage from the dashboard
4. what the system uses for filming or producing the final video

The goal is to describe the current shipped behavior, not the intended future product.

## Short Answer

The content-generation pipeline produces structured planning and execution artifacts for short-form video creation, not a finished video file. The canonical run container is `PipelineContext`, which holds strategy memory, opportunity brief, backlog, scoring, angles, research pack, argument map, scripting output, visual plan, production brief, packaging, QC gate, publish items, performance analysis, stage traces, and claim traceability data.

"Persistence" means saving those resources or run states to disk so they survive process restarts and can be reloaded or resumed later. In practice, the code currently persists strategy memory, standalone script runs, publish queue entries, and browser-started pipeline jobs with their saved `PipelineContext`. Some individual stage outputs are still operator-managed unless explicitly saved.

The dashboard can start, stop, inspect, and resume content-generation pipeline runs; show detailed per-stage outputs; manage the backlog; edit strategy memory; inspect saved scripts; approve QC for publish; remove items from the publish queue; and use AI-assisted backlog chat, triage, next-action, and execution-brief tools. The global dashboard settings page can also edit persisted application config, secrets, search-cache settings, and model-routing-related runtime config for future runs.

The system does not actually film, record, or render the final video. It generates a `VisualPlanOutput` and then a `ProductionBrief` that tells a human operator what to shoot, what props/assets to prepare, what setup to use, and what pickup lines to capture. There is no in-repo video renderer or capture stack such as `ffmpeg`, `moviepy`, `remotion`, or `shotstack`.

## Core Pipeline Container

The canonical full-run artifact is [`PipelineContext`](src/cc_deep_research/content_gen/models.py), defined in [`src/cc_deep_research/content_gen/models.py`](src/cc_deep_research/content_gen/models.py). It is the accumulated state for the full content pipeline and is the main object that gets saved for resumable pipeline runs.

`PipelineContext` currently contains these major fields:

| Field | Meaning |
| --- | --- |
| `pipeline_id` | Stable identifier for the pipeline run |
| `theme` | Top-level theme or operator-provided starting point |
| `current_stage` | Current pipeline stage index |
| `strategy` | Persistent strategy memory |
| `opportunity_brief` | Editorial framing artifact from theme -> opportunity planning |
| `backlog` | Generated backlog ideas |
| `scoring` | Scoring output over backlog items |
| `shortlist` | Chosen shortlist of idea ids |
| `selected_idea_id` | Primary idea being executed |
| `runner_up_idea_ids` | Additional preserved candidate ids |
| `active_candidates` | Small candidate queue for primary and runner-up lanes |
| `lane_contexts` | Lane-specific context data for candidate execution paths |
| `angles` | Generated angle options for the selected idea |
| `research_pack` | Compact evidence pack for scripting and QC |
| `argument_map` | Claim/proof/narrative plan |
| `scripting` | Nested 10-step script-generation state |
| `visual_plan` | Beat-by-beat visual treatment |
| `production_brief` | Filming checklist and production prep |
| `execution_brief` | P5-T2: Combined visual and production brief for low/medium complexity formats |
| `packaging` | Platform-specific hooks, captions, hashtags, and related package data |
| `qc_gate` | AI-assisted QC review plus human approval gate |
| `publish_items` | Publish schedule suggestions and engagement plans |
| `performance` | Post-publish analysis artifact |
| `iteration_state` | Iterative scripting-quality loop state |
| `stage_traces` | Observability records for each stage |
| `claim_ledger` | Traceability ledger for claims and proof support |

Relevant source:

- [`src/cc_deep_research/content_gen/models.py`](src/cc_deep_research/content_gen/models.py)
- [`docs/content-generation.md`](docs/content-generation.md)

## Pipeline Artifact Inventory

The implemented pipeline order is documented in [`docs/content-generation.md`](docs/content-generation.md) and represented in code by `PIPELINE_STAGES`.

The current full content-generation flow is:

1. `load_strategy`
2. `plan_opportunity`
3. `build_backlog`
4. `score_ideas`
5. `generate_angles`
6. `build_research_pack`
7. `build_argument_map`
8. `run_scripting`
9. `visual_translation`
10. `production_brief`
11. `packaging`
12. `human_qc`
13. `publish_queue`
14. `performance_analysis`

### Stage-by-Stage Artifact Table

| Stage | Artifact / Model | What it contains | Default persistence behavior |
| --- | --- | --- | --- |
| Strategy load | `StrategyMemory` | Niche, pillars, platforms, tone rules, proof standards, winners/losers, performance guidance | Persisted to YAML via `StrategyStore` |
| Opportunity planning | `OpportunityBrief` | Goal, audience segments, problem statements, proof requirements, hypotheses, success criteria | Held in `PipelineContext`; saved when pipeline context is persisted |
| Backlog build | `BacklogOutput` | Candidate ideas, rejection counts, rejection reasons, degradation metadata | Incomplete by default for CLI-generated backlog unless explicitly saved; can be persisted via backlog service/store |
| Idea scoring | `ScoringOutput` | Per-idea scores, shortlist, selected idea, runner-ups, recommendations | Held in `PipelineContext`; scoring metadata can be applied to persisted backlog |
| Angle generation | `AngleOutput` | Multiple editorial framings for one idea plus selected angle | Held in `PipelineContext`; operator-managed if saved as standalone JSON |
| Research pack | `ResearchPack` | Audience insights, competitor observations, facts, proof points, examples, gaps, claims requiring verification, source-backed research summary | Held in `PipelineContext`; operator-managed if saved as standalone JSON |
| Argument map | `ArgumentMap` | Thesis, proof anchors, safe claims, unsafe claims, counterarguments, beat-claim plan | Held in `PipelineContext` |
| Scripting | `ScriptingContext` | All 10 scripting steps, hooks, drafts, tightened script, visual notes, QC result, LLM traces | Standalone scripting runs are autosaved by `ScriptingStore`; pipeline uses nested `ScriptingContext` inside `PipelineContext` |
| Visual translation | `VisualPlanOutput` | Beat-by-beat visual treatment and refresh check | Held in `PipelineContext`; can also be saved as standalone JSON |
| Production brief | `ProductionBrief` | Location, setup, wardrobe, props, prep assets, audio/battery/storage checks, pickup lines, backup plan | Held in `PipelineContext`; can also be saved as standalone JSON |
| Packaging | `PackagingOutput` | Per-platform hooks, captions, keywords, hashtags, pinned comments, CTAs, notes | Held in `PipelineContext`; can also be saved as standalone JSON |
| Human QC | `HumanQCGate` | Hook strength, issue lists, fact-check flags, must-fix items, human approval flag | Held in `PipelineContext`; approval can be mutated from dashboard or CLI |
| Publish queue | `PublishItem` list | Suggested publish datetimes and first-30-minute engagement plans | Persisted in YAML via `PublishQueueStore`; also retained in `PipelineContext.publish_items` |
| Performance analysis | `PerformanceAnalysis` | What worked, what failed, audience signals, drop-off hypotheses, hook diagnosis, lessons, next tests, follow-up ideas | Not auto-run by the all-in-one pipeline; usually operator-managed from real post-publish metrics |

## Important Non-Content Artifacts

The content pipeline also produces operational artifacts that matter even when they are not "creative outputs."

### 1. `PipelineStageTrace`

Each completed stage can emit a trace record with:

- stage index and stage name
- status: completed, skipped, or failed
- start and completion times
- duration
- input summary
- output summary
- warnings
- decision summary
- structured metadata

This is what powers much of the dashboard observability layer.

### 2. `claim_ledger`

The claim traceability ledger tracks where important claims came from and whether they remained supported from research through scripting. This is useful for factual safety, QC, and operator trust.

### 3. Candidate queue and lane state

The pipeline preserves:

- a primary idea
- a small top-2 candidate queue
- explicit runner-up identifiers
- per-lane context containers

The important caveat is that downstream automation still executes only the primary lane in normal runs.

## What Persistence Means Here

In this repo, "persistence" means that generated state is written to local storage so it can survive:

- app restarts
- CLI exits
- browser refreshes
- failed or interrupted jobs
- later operator review or resume

Persistence is not one thing. There are several layers:

1. durable domain objects saved to local YAML or JSON
2. persisted pipeline jobs for browser-started runs
3. saved standalone script runs
4. optional operator-managed stage JSON files
5. persisted application config and secrets managed from the dashboard settings page

## Persistence Backends and Default Paths

### Strategy memory

- Store class: [`StrategyStore`](src/cc_deep_research/content_gen/storage/strategy_store.py)
- Format: YAML
- Default path: `~/.config/cc-deep-research/strategy.yaml`

### Backlog

- Store class: [`BacklogStore`](src/cc_deep_research/content_gen/storage/backlog_store.py)
- Format: YAML
- Default path resolution comes from content-gen path helpers and config
- Important caveat: backlog storage exists, but not every CLI backlog command auto-persists generated outputs to it

### Standalone scripts

- Store class: [`ScriptingStore`](src/cc_deep_research/content_gen/storage/scripting_store.py)
- Format: text plus JSON
- Default directory: `~/.config/cc-deep-research/scripts/`

Saved scripting outputs include:

- `latest.txt`
- `latest.context.json`
- `latest.result.json`
- `latest.json`
- per-run directories under `scripts/<run_id>/`

Each per-run directory stores:

- `script.txt`
- `context.json`
- `result.json`
- `metadata.json`

### Publish queue

- Store class: [`PublishQueueStore`](src/cc_deep_research/content_gen/storage/publish_queue_store.py)
- Format: YAML
- Default path: `~/.config/cc-deep-research/publish_queue.yaml`

### Browser-started pipeline jobs

- Store class: `PipelineRunStore`
- Runtime registry: `PipelineRunJobRegistry`
- Format: JSON
- Default directory: `~/.config/cc-deep-research/content-gen/pipelines/`

Each saved job includes:

- `pipeline_id`
- theme
- from/to stage
- status
- serialized `PipelineContext`
- error
- created, started, and completed timestamps
- stop-request state

This is the key persistence layer that makes dashboard-started pipeline runs durable and resumable.

## What Is Persisted Automatically Today

### Automatically persisted in normal workflow

These are wired into the current system behavior:

| Resource | Persisted automatically | Notes |
| --- | --- | --- |
| Strategy memory | Yes | Saved via `StrategyStore` |
| Standalone scripting runs | Yes | Autosaved via `ScriptingStore` |
| Publish queue | Yes | Saved via `PublishQueueStore` |
| Browser-started pipeline jobs | Yes | Saved as durable job records with serialized `PipelineContext` |
| Dashboard pipeline context snapshots | Yes | Updated after stage completion and on final completion |
| CLI pipeline context | Yes, when configured | Checkpoint-style context saves happen if output/save-context is configured |
| Partial CLI pipeline context on failure | Best effort | The latest resumable context can be written even when later stages fail |

### Not fully automatic yet

These are not uniformly persisted as first-class managed resources:

| Resource | Current state |
| --- | --- |
| Backlog build output from CLI | Often file-based unless operator saves explicitly |
| Scoring output from CLI | Often file-based unless operator saves explicitly |
| Angles JSON | Operator-managed |
| Research pack JSON | Operator-managed |
| Visual plan JSON | Operator-managed |
| Production brief JSON | Operator-managed |
| Packaging JSON | Operator-managed |
| Performance JSON | Operator-managed |

The repo docs explicitly call out that stage artifacts remain uneven even though pipeline-context persistence is now durable.

## Resume and Recovery Behavior

The browser-started pipeline job system is designed so a run does not disappear after interruption.

What happens operationally:

- a dashboard-started pipeline run is persisted as a job JSON file
- the latest `PipelineContext` is updated after stage completion
- if the app restarts while the run was queued or running, the registry marks that job as failed/interrupted rather than losing it
- the saved context remains available for inspection and resume
- resuming creates a distinct resume job id instead of overwriting the original run record

This matters because persistence here is not just for historical storage. It is also the mechanism that makes operator recovery possible.

## Dashboard-Manageable Surfaces

There are two dashboard stories in this repo:

1. the browser-first operational dashboard built from FastAPI plus Next.js
2. the older Streamlit telemetry dashboard used for historical analytics

When discussing "manage via dashboard" for content generation, the browser dashboard is the relevant one.

## Content Studio Surfaces

The Content Studio shell currently exposes these major tabs:

- `Overview`
- `Scripts`
- `Strategy`
- `Queue`
- `Backlog`
- `Assistant`

These are defined in [`dashboard/src/components/content-gen/content-gen-shell.tsx`](dashboard/src/components/content-gen/content-gen-shell.tsx).

### Overview

The overview surface is the operational entry point for content generation. It is used for:

- starting a new pipeline
- seeing active and past pipeline runs
- opening pipeline detail pages
- bridging research output into content generation
- opening quick-script workflows

### Scripts

The scripts view is a saved-script history surface. It can:

- list saved script runs
- expand and load a full saved script result
- inspect the final script and process trace
- reuse prior raw inputs

### Strategy

The strategy editor is the operator surface for strategy memory. It currently supports:

- loading the saved strategy
- editing niche
- editing content pillars
- editing tone rules
- editing platforms
- editing forbidden claims
- editing proof standards
- saving the patch back to persistence
- exporting strategy as JSON
- copying strategy JSON
- importing strategy JSON into the UI

The frontend component is [`dashboard/src/components/content-gen/strategy-editor.tsx`](dashboard/src/components/content-gen/strategy-editor.tsx), and the backend writes through `/api/content-gen/strategy`.

### Queue

The publish queue surface can:

- list publish items
- inspect scheduled time and status by platform
- remove queue items

It is a queue-management surface, not an actual platform publisher.

### Backlog

The backlog workspace is one of the most operator-active parts of the dashboard. It can:

- list persistent backlog items
- filter by status and category
- create new backlog items
- edit backlog items
- select an item
- archive an item
- delete an item
- start production for a single backlog item
- navigate into a backlog detail page

The backlog detail and related AI helpers add more capabilities:

- AI-assisted backlog chat with explicit apply flow
- AI batch triage proposals with explicit apply flow
- next-action recommendations
- execution-brief generation

Important architectural point: the AI chat and triage endpoints are advisory first. Persisted changes happen only through explicit apply routes.

### Assistant

The assistant route is the conversational backlog workspace. It is designed for:

- discussing backlog changes with an LLM
- reviewing proposed operations
- explicitly applying accepted operations

This is a management surface for editorial backlog state, not a passive chat transcript viewer.

## Pipeline Detail Page

The pipeline detail page at `/content-gen/pipeline/[id]` is the main observability and control surface for an individual content-generation run.

It currently supports:

- viewing pipeline header and status
- viewing current stage and per-stage progress
- seeing completed, skipped, and failed stage counts
- inspecting warnings and degradation indicators
- viewing trace metadata such as counts and decision summaries
- inspecting full stage outputs for each pipeline artifact
- viewing the final script
- inspecting the full scripting step trace with prompts, providers, models, raw responses, and parsed outputs
- monitoring live updates via WebSocket
- stopping active runs
- resuming stopped or failed runs through the API-backed flow

The stage output panels are already wired to show:

- strategy memory
- opportunity brief
- backlog
- scoring
- angles
- research pack
- scripting details
- visual plan
- production brief
- packaging
- human QC
- publish queue
- performance analysis

## Global Settings Page

Outside Content Studio, the dashboard settings page manages persisted application config.

It is not content-gen-only, but it directly affects future content-gen runs because it controls app-level behavior and routing.

The settings page supports:

- editing persisted config
- reviewing persisted versus effective config
- seeing environment-variable overrides
- changing research defaults
- changing execution and output config
- changing model-routing-related config
- managing secrets
- managing search-cache controls

Important behavioral rule:

- changes apply to future runs only
- active runs keep the config that was resolved when they started

## Dashboard API Capabilities

The backend routes in [`src/cc_deep_research/content_gen/router.py`](src/cc_deep_research/content_gen/router.py) show the practical management surface exposed to the dashboard.

### Pipeline control endpoints

- `GET /api/content-gen/pipelines`
- `POST /api/content-gen/pipelines`
- `GET /api/content-gen/pipelines/{pipeline_id}`
- `POST /api/content-gen/pipelines/{pipeline_id}/stop`
- `POST /api/content-gen/pipelines/{pipeline_id}/resume`

These allow listing, starting, viewing, stopping, and resuming pipeline runs.

### QC control

- `POST /api/content-gen/qc/{pipeline_id}/approve`

This flips `approved_for_publish` to `true` on the saved pipeline context.

### Saved scripts

- `GET /api/content-gen/scripts`
- `GET /api/content-gen/scripts/{run_id}`

These allow script history inspection.

### Backlog management

- `POST /api/content-gen/backlog`
- `GET /api/content-gen/backlog`
- `PATCH /api/content-gen/backlog/{idea_id}`
- `POST /api/content-gen/backlog/{idea_id}/select`
- `POST /api/content-gen/backlog/{idea_id}/archive`
- `DELETE /api/content-gen/backlog/{idea_id}`
- `POST /api/content-gen/backlog/{idea_id}/start`

These routes make the dashboard a real editorial management surface, not just a run monitor.

### AI-assisted backlog management

- `POST /api/content-gen/backlog-chat/respond`
- `POST /api/content-gen/backlog-chat/apply`
- `POST /api/content-gen/backlog-ai/triage/respond`
- `POST /api/content-gen/backlog-ai/triage/apply`
- `POST /api/content-gen/backlog-ai/next-action`
- `POST /api/content-gen/backlog-ai/next-action/batch`
- `POST /api/content-gen/backlog-ai/execution-brief`

These routes support operator-in-the-loop AI workflows for editorial planning and backlog refinement.

### Strategy and publish queue

- `GET /api/content-gen/strategy`
- `PUT /api/content-gen/strategy`
- `GET /api/content-gen/publish`
- `DELETE /api/content-gen/publish/{idea_id}/{platform}`

### Live pipeline monitoring

- `WS /ws/content-gen/pipeline/{pipeline_id}`

This is how the dashboard receives live stage-started, stage-completed, stage-failed, and stage-skipped events, plus the latest serialized `PipelineContext`.

## What the System Uses to Film the Video

The strict answer is: it does not film the video.

The content-generation subsystem stops at planning, scripting, QC, publish scheduling, and post-publish analysis. It creates the materials a person or external production workflow would use to shoot and publish the video, but it does not contain an actual in-repo filming or rendering engine.

### What it does generate for production

The repo generates two artifacts that matter directly for shooting:

#### 1. `VisualPlanOutput`

This is the visual treatment artifact. It provides beat-by-beat visual guidance, including the visual refresh signal and structured beat visuals.

This is the bridge between the written script and the shoot plan.

#### 2. `VisualProductionExecutionBrief` (P5-T2 & P5-T3)

For formats where `use_combined_execution_brief=True` (newsletter, article, thread, carousel), the system generates a combined execution brief instead of separate visual and production artifacts. This brief covers:

- Beat-to-visual mapping (simplified or full depending on `visual_complexity`)
- Production constraints (location, setup, wardrobe, props)
- Fallback options for missing assets (P5-T3)
- Asset reuse paths from existing library (P5-T3)
- Owner assignments and shoot constraints
- Missing asset decisions (downgrade, delay, alt-format, or skip)

This reduces planning overhead for light assets while preserving full planning for complex formats.

#### 3. `ProductionBrief`

This is the filming checklist artifact. It contains:

- `location`
- `setup`
- `wardrobe`
- `props`
- `assets_to_prepare`
- `audio_checks`
- `battery_checks`
- `storage_checks`
- `pickup_lines_to_capture`
- `backup_plan`

In plain terms, this is the thing you would hand to the human shooting or producing the video.

### What the prompt explicitly says

The production prompt explicitly frames the task as generating a production brief so filming is "idiot-proof." It asks for:

- where to film
- camera, lighting, and mic setup
- wardrobe
- props
- assets to prepare
- audio, battery, and storage checks
- pickup lines
- a backup plan

That is strong evidence that the repository is designed to support human filming execution, not replace it.

### What I did not find

I did not find a repo-native stack for:

- direct camera capture
- automated video recording
- video compositing
- video rendering
- timeline editing
- final export generation

I also did not find dependencies or code paths for common video stacks such as:

- `ffmpeg`
- `moviepy`
- `opencv`
- `remotion`
- `shotstack`

The Python dependencies in [`pyproject.toml`](pyproject.toml) and the frontend dependencies in [`dashboard/package.json`](dashboard/package.json) do not define a video rendering pipeline.

## Practical Interpretation

If someone asks, "What are the artifacts of the content-generation pipeline?" the practical answer is:

- strategy and planning artifacts
- ideation and selection artifacts
- research and claim-grounding artifacts
- script-generation artifacts
- visual and production-planning artifacts
- packaging and publish-planning artifacts
- QC and performance-learning artifacts
- observability and resume artifacts

If someone asks, "What is persistence?" the practical answer is:

- the durable storage of strategy, scripts, publish queue, and browser-started pipeline jobs with saved `PipelineContext`, plus optional saved stage outputs

If someone asks, "What can we manage via dashboard?" the practical answer is:

- pipeline runs
- saved scripts
- strategy memory
- backlog records
- AI-assisted backlog workflows
- QC approval
- publish queue items
- global persisted application config and secrets

If someone asks, "What do we use to film the video?" the practical answer is:

- we do not film it in code
- we generate the visual plan and production brief that a human or an external toolchain would use to shoot it

## Important Caveats

### 1. The all-in-one pipeline is not a one-command publish system

The docs are explicit that normal pipeline runs still stop before publish unless there is an explicit human approval pass.

### 2. Performance analysis is not part of automatic end-to-end generation

The full automatic pipeline does not run performance analysis because that stage depends on real post-publish metrics.

### 3. Stage artifact persistence is still uneven

Even though pipeline-context persistence is durable, standalone stage artifacts are still a mix of autosaved resources and operator-managed files.

### 4. The dashboard is both an observability tool and a control plane

It is not just a viewer. It can mutate persistent state in several places:

- strategy updates
- backlog CRUD and status changes
- QC approval
- publish queue removal
- pipeline start/stop/resume
- AI apply flows for backlog operations

## Source Map

Main implementation and documentation references used for this note:

- [`docs/content-generation.md`](docs/content-generation.md)
- [`docs/DASHBOARD_GUIDE.md`](docs/DASHBOARD_GUIDE.md)
- [`src/cc_deep_research/content_gen/models.py`](src/cc_deep_research/content_gen/models.py)
- [`src/cc_deep_research/content_gen/progress.py`](src/cc_deep_research/content_gen/progress.py)
- [`src/cc_deep_research/content_gen/router.py`](src/cc_deep_research/content_gen/router.py)
- [`src/cc_deep_research/content_gen/storage/strategy_store.py`](src/cc_deep_research/content_gen/storage/strategy_store.py)
- [`src/cc_deep_research/content_gen/storage/backlog_store.py`](src/cc_deep_research/content_gen/storage/backlog_store.py)
- [`src/cc_deep_research/content_gen/storage/scripting_store.py`](src/cc_deep_research/content_gen/storage/scripting_store.py)
- [`src/cc_deep_research/content_gen/storage/publish_queue_store.py`](src/cc_deep_research/content_gen/storage/publish_queue_store.py)
- [`src/cc_deep_research/content_gen/prompts/production.py`](src/cc_deep_research/content_gen/prompts/production.py)
- [`dashboard/src/components/content-gen/content-gen-shell.tsx`](dashboard/src/components/content-gen/content-gen-shell.tsx)
- [`dashboard/src/components/content-gen/strategy-editor.tsx`](dashboard/src/components/content-gen/strategy-editor.tsx)
- [`dashboard/src/components/content-gen/scripts-panel.tsx`](dashboard/src/components/content-gen/scripts-panel.tsx)
- [`dashboard/src/components/content-gen/backlog-panel.tsx`](dashboard/src/components/content-gen/backlog-panel.tsx)
- [`dashboard/src/components/content-gen/publish-queue-panel.tsx`](dashboard/src/components/content-gen/publish-queue-panel.tsx)
- [`dashboard/src/components/content-gen/qc-gate-panel.tsx`](dashboard/src/components/content-gen/qc-gate-panel.tsx)
- [`pyproject.toml`](pyproject.toml)
- [`dashboard/package.json`](dashboard/package.json)
