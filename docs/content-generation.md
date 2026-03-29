# Content-Generation Workflow

This document describes the full content-generation system as it is currently implemented in `cc-deep-research`. It covers the architecture, the stage-by-stage flow, the CLI entrypoints, the saved artifacts, and the places where the intended product workflow is ahead of the shipped code.

## Scope

The content-generation subsystem is separate from the research-report pipeline. It lives under [`src/cc_deep_research/content_gen/`](../src/cc_deep_research/content_gen/) and is focused on short-form video creation:

- persistent strategy memory
- idea backlog generation and scoring
- angle development
- compact research-pack synthesis
- multi-step script generation
- visual planning
- production planning
- packaging
- human QC
- publish scheduling
- post-publish performance review

At the center is [`ContentGenOrchestrator`](../src/cc_deep_research/content_gen/orchestrator.py), which coordinates individual stage agents and accumulates outputs into [`PipelineContext`](../src/cc_deep_research/content_gen/models.py).

## Architecture At A Glance

The system has three layers:

1. CLI layer
   Exposed through `cc-deep-research content-gen ...` in [`src/cc_deep_research/content_gen/cli.py`](../src/cc_deep_research/content_gen/cli.py).
2. Orchestration layer
   [`ContentGenOrchestrator`](../src/cc_deep_research/content_gen/orchestrator.py) runs either standalone modules or the full pipeline.
3. Agent layer
   Each stage has its own prompt module and LLM-backed agent under [`src/cc_deep_research/content_gen/agents/`](../src/cc_deep_research/content_gen/agents/).

Supporting layers:

- data contracts: [`src/cc_deep_research/content_gen/models.py`](../src/cc_deep_research/content_gen/models.py)
- prompt templates: [`src/cc_deep_research/content_gen/prompts/`](../src/cc_deep_research/content_gen/prompts/)
- local persistence: [`src/cc_deep_research/content_gen/storage/`](../src/cc_deep_research/content_gen/storage/)
- LLM routing: [`src/cc_deep_research/llm/`](../src/cc_deep_research/llm/)
- search providers for research-pack synthesis: [`src/cc_deep_research/providers/`](../src/cc_deep_research/providers/)

## Core Design Pattern

Every content stage follows the same pattern:

1. Build a prompt from structured input models.
2. Send it through `LLMRouter`.
3. Parse plain-text output back into Pydantic models using lightweight regex helpers.
4. Return the structured stage output to the orchestrator or CLI.

That design keeps the implementation simple, but it has consequences:

- the prompt format is part of the parsing contract
- most stages depend on delimiter blocks like `---` and `field_name: value`
- if prompt wording changes, the parser may also need to change
- empty or malformed LLM output can degrade into partial or blank models

The scripting agent is the strictest implementation. It validates missing fields aggressively and raises `ValueError` when required outputs are absent. Most other agents are more permissive and will often return sparse models instead of failing fast.

## Main Data Models

The workflow revolves around two context objects:

- [`PipelineContext`](../src/cc_deep_research/content_gen/models.py)
  The top-level 12-stage pipeline state.
- [`ScriptingContext`](../src/cc_deep_research/content_gen/models.py)
  The nested 10-step script-generation state machine.

Important stage models:

- `StrategyMemory`
- `BacklogOutput` and `BacklogItem`
- `ScoringOutput` and `IdeaScores`
- `AngleOutput` and `AngleOption`
- `ResearchPack`
- `VisualPlanOutput`
- `ProductionBrief`
- `PackagingOutput` and `PlatformPackage`
- `HumanQCGate`
- `PublishItem`
- `PerformanceAnalysis`

## Workflow Shapes

There are three practical ways to use the subsystem.

### 1. Standalone module execution

Run one stage at a time with explicit file handoffs:

- `content-gen backlog build`
- `content-gen backlog score`
- `content-gen angle generate`
- `content-gen research`
- `content-gen script`
- `content-gen visual`
- `content-gen production`
- `content-gen package`
- `content-gen qc review`
- `content-gen publish schedule`
- `content-gen performance`

This is the most reliable operator workflow today because you control each artifact explicitly.

### 2. Script-only workflow

Run the dedicated 10-step script pipeline:

```bash
cc-deep-research content-gen script --idea "..."
```

This path is more mature than the rest of the full pipeline. It autosaves outputs and supports step-based resume.

### 3. Full pipeline execution

Run the 12-stage orchestrated flow:

```bash
cc-deep-research content-gen pipeline --theme "..."
```

This path works for generation up through QC, but it currently has important gaps documented below in [Current Gaps And Caveats](#current-gaps-and-caveats).

## End-To-End Flow

The implemented pipeline order is defined by `PIPELINE_STAGES` in [`src/cc_deep_research/content_gen/models.py`](../src/cc_deep_research/content_gen/models.py):

1. `load_strategy`
2. `build_backlog`
3. `score_ideas`
4. `generate_angles`
5. `build_research_pack`
6. `run_scripting`
7. `visual_translation`
8. `production_brief`
9. `packaging`
10. `human_qc`
11. `publish_queue`
12. `performance_analysis`

Operationally, the flow looks like this:

```text
strategy memory
  -> backlog ideas
  -> scored shortlist
  -> one selected idea
  -> multiple angles
  -> one chosen angle
  -> research pack
  -> nested scripting pipeline
  -> visual plan
  -> production brief
  -> packaging variants
  -> AI QC gate
  -> human approval
  -> publish queue
  -> performance analysis
  -> feedback into strategy/backlog decisions
```

## Stage-By-Stage Breakdown

### Stage 0: Strategy Memory

Implementation:

- model: `StrategyMemory`
- store: [`StrategyStore`](../src/cc_deep_research/content_gen/storage/strategy_store.py)
- default path: `~/.config/cc-deep-research/strategy.yaml`
- CLI group: `content-gen strategy`

Purpose:

- preserve niche, pillars, audience segments, tone rules, platform rules, proof standards, and examples across runs
- stop the system from reinventing editorial identity every time

CLI:

```bash
cc-deep-research content-gen strategy init
cc-deep-research content-gen strategy show
cc-deep-research content-gen strategy set niche "B2B SaaS"
cc-deep-research content-gen strategy set content_pillars "pricing,positioning,retention"
```

Notes:

- `strategy set` only supports shallow scalar updates and a few comma-separated list fields
- nested structures like `audience_segments` are not managed ergonomically through the CLI yet

### Stage 1: Backlog Builder

Implementation:

- agent: [`BacklogAgent`](../src/cc_deep_research/content_gen/agents/backlog.py)
- prompt: [`prompts/backlog.py`](../src/cc_deep_research/content_gen/prompts/backlog.py)
- model output: `BacklogOutput`

Purpose:

- generate idea candidates across `trend-responsive`, `evergreen`, and `authority-building`
- reject vague, unprovable, or overly broad ideas

Input sources:

- theme
- strategy memory
- optionally past winners already stored in strategy memory

Selection logic:

- every idea should include audience, problem, why-now framing, hook, and evidence
- rejection counts and reasons are extracted from the raw LLM response

CLI:

```bash
cc-deep-research content-gen backlog build --theme "pricing psychology" --count 20 -o backlog.json
```

Persistence behavior:

- the command prints results and can save JSON with `-o`
- it does not automatically persist to [`BacklogStore`](../src/cc_deep_research/content_gen/storage/backlog_store.py)

### Stage 2: Idea Scoring

Implementation:

- same agent: [`BacklogAgent`](../src/cc_deep_research/content_gen/agents/backlog.py)
- output model: `ScoringOutput`

Scoring dimensions:

- relevance
- novelty
- authority fit
- production ease
- evidence strength
- hook strength
- repurposing

Threshold behavior:

- default threshold comes from `config.content_gen.scoring_threshold_produce`
- current default is `25`

CLI:

```bash
cc-deep-research content-gen backlog score --from-file backlog.json --select-top 5 -o scoring.json
```

Pipeline behavior:

- the full pipeline takes the first `produce_now` idea only
- it does not currently branch into multiple ideas or keep a ranked work queue inside the pipeline context

### Stage 3: Angle Generation

Implementation:

- agent: [`AngleAgent`](../src/cc_deep_research/content_gen/agents/angle.py)
- prompt: [`prompts/angle.py`](../src/cc_deep_research/content_gen/prompts/angle.py)
- output model: `AngleOutput`

Purpose:

- turn one backlog idea into several distinct editorial framings
- separate topic choice from angle choice

Selection logic:

- prompt asks for 3-5 options
- parser extracts all angle blocks
- `selected_angle_id` and `selection_reasoning` are read from the summary section

CLI:

```bash
cc-deep-research content-gen angle generate \
  --idea "Why most SaaS onboarding fails after day 1" \
  --audience "seed-stage SaaS founders" \
  --problem "activation drops after signup" \
  -o angles.json
```

Pipeline behavior:

- if `selected_angle_id` is present, the pipeline uses it
- otherwise it falls back to the first angle option

### Stage 4: Research Pack Builder

Implementation:

- agent: [`ResearchPackAgent`](../src/cc_deep_research/content_gen/agents/research_pack.py)
- prompt: [`prompts/research_pack.py`](../src/cc_deep_research/content_gen/prompts/research_pack.py)
- output model: `ResearchPack`

Purpose:

- produce enough evidence to support the content without drifting into open-ended research

How it works:

1. Build a small query set from the idea and angle.
2. Run those queries through the configured search providers.
3. Convert snippets into a compact search context string.
4. Ask the LLM to synthesize audience insights, proof points, gaps, and risk flags.

Configuration:

- `config.content_gen.research_max_queries`
- current default: `6`

CLI:

```bash
cc-deep-research content-gen research \
  --idea "Why most SaaS onboarding fails after day 1" \
  --angle "Fix activation by removing the false success moment" \
  -o research.json
```

Important implementation details:

- provider setup is shared with the research subsystem
- query generation is heuristic and intentionally small
- one built-in query template is still hard-coded to `content trends 2025`, which is stale and should be treated as technical debt
- the stored research pack is compact by design and not a citation-grade source graph

### Stage 5: Scripting Pipeline

Implementation:

- agent: [`ScriptingAgent`](../src/cc_deep_research/content_gen/agents/scripting.py)
- prompt module: [`prompts/scripting.py`](../src/cc_deep_research/content_gen/prompts/scripting.py)
- context model: `ScriptingContext`
- autosave store: [`ScriptingStore`](../src/cc_deep_research/content_gen/storage/scripting_store.py)

This is the most detailed sub-workflow in the system. It has 10 explicit steps:

1. define core inputs
2. define angle
3. choose structure
4. define beat intents
5. generate hooks
6. draft script
7. add retention mechanics
8. tighten
9. add visual notes
10. run QC

CLI:

```bash
cc-deep-research content-gen script --idea "..." -o script.txt --save-context
cc-deep-research content-gen script --from-file script.context.json --from-step 6
cc-deep-research content-gen scripts list
cc-deep-research content-gen scripts show --latest
```

Autosaved artifacts:

- `~/.config/cc-deep-research/scripts/latest.txt`
- `~/.config/cc-deep-research/scripts/latest.context.json`
- `~/.config/cc-deep-research/scripts/latest.json`
- per-run directories under `~/.config/cc-deep-research/scripts/<run_id>/`

How the full pipeline uses it:

- the full pipeline does not start scripting from raw idea
- it seeds a `ScriptingContext` with:
  - `raw_idea`
  - `research_context`
  - precomputed `core_inputs`
  - precomputed `angle`
- then it resumes the scripting workflow from step `3`, which is `choose_structure`

That means the full pipeline treats the earlier backlog, angle, and research stages as the upstream planning work for the scripting engine.

### Stage 6: Visual Translation

Implementation:

- agent: [`VisualAgent`](../src/cc_deep_research/content_gen/agents/visual.py)
- prompt: [`prompts/visual.py`](../src/cc_deep_research/content_gen/prompts/visual.py)
- output model: `VisualPlanOutput`

Inputs:

- a script version
- a beat list from script structure

Behavior:

- the orchestrator prefers `tightened`, then `annotated_script`, then `draft`
- each beat is expanded into a visual treatment
- the prompt asks for a `visual_refresh_check`

CLI:

```bash
cc-deep-research content-gen visual --from-file script.context.json -o visual.json
```

Guardrail:

- this stage requires both a script and a structure
- if either is missing, the standalone orchestrator call raises a `ValueError`

### Stage 7: Production Brief

Implementation:

- agent: [`ProductionAgent`](../src/cc_deep_research/content_gen/agents/production.py)
- prompt: [`prompts/production.py`](../src/cc_deep_research/content_gen/prompts/production.py)
- output model: `ProductionBrief`

Purpose:

- convert the visual plan into a concrete filming checklist
- reduce missed assets, missed pickup lines, and setup mistakes

CLI:

```bash
cc-deep-research content-gen production --from-file visual.json -o production.json
```

### Stage 8: Packaging

Implementation:

- agent: [`PackagingAgent`](../src/cc_deep_research/content_gen/agents/packaging.py)
- prompt: [`prompts/packaging.py`](../src/cc_deep_research/content_gen/prompts/packaging.py)
- output model: `PackagingOutput`

Purpose:

- create platform-specific hooks, cover text, captions, keywords, hashtags, pinned comments, and CTAs

Configuration:

- `config.content_gen.default_platforms`
- current default: `["tiktok", "reels", "shorts"]`

CLI:

```bash
cc-deep-research content-gen package --from-file script.context.json -o packaging.json
cc-deep-research content-gen package --from-file pipeline.context.json --platforms "tiktok,shorts"
```

Input behavior:

- the CLI accepts either a scripting context or a full pipeline context
- helper functions extract the best available final script and angle information

### Stage 9: Human QC Gate

Implementation:

- agent: [`QCAgent`](../src/cc_deep_research/content_gen/agents/qc.py)
- prompt: [`prompts/qc.py`](../src/cc_deep_research/content_gen/prompts/qc.py)
- output model: `HumanQCGate`

Purpose:

- produce an AI-assisted review
- never auto-approve publishing

Important rule:

- `approved_for_publish` defaults to `False`
- the AI review never changes that
- human approval is a separate explicit step

CLI:

```bash
cc-deep-research content-gen qc review --from-file pipeline.context.json
cc-deep-research content-gen qc approve --idea-id idea123 --from-file pipeline.context.json
```

Current behavior:

- `qc review` runs a fresh review from the saved context
- `qc approve` mutates the saved context JSON by flipping `approved_for_publish` to `True`

### Stage 10: Publish Queue

Implementation:

- agent: [`PublishAgent`](../src/cc_deep_research/content_gen/agents/publish.py)
- prompt: [`prompts/publish.py`](../src/cc_deep_research/content_gen/prompts/publish.py)
- persistent store: [`PublishQueueStore`](../src/cc_deep_research/content_gen/storage/publish_queue_store.py)
- output model: `PublishItem`

Purpose:

- generate scheduling suggestions and first-30-minute engagement actions
- persist queued publish entries

CLI:

```bash
cc-deep-research content-gen publish schedule --from-file packaging.json --idea-id idea123
cc-deep-research content-gen publish list
```

Persistence:

- default queue path: `~/.config/cc-deep-research/publish_queue.yaml`

Important detail:

- the standalone publish path persists every generated publish item
- the full pipeline only stores the first generated `PublishItem` in `PipelineContext`

### Stage 11: Performance Analysis

Implementation:

- agent: [`PerformanceAgent`](../src/cc_deep_research/content_gen/agents/performance.py)
- prompt: [`prompts/performance.py`](../src/cc_deep_research/content_gen/prompts/performance.py)
- output model: `PerformanceAnalysis`

Purpose:

- analyze what worked and what failed after publication
- generate the next test and follow-up ideas

CLI:

```bash
cc-deep-research content-gen performance \
  --video-id "tt_123" \
  --metrics-file metrics.json \
  --script "..." \
  -o performance.json
```

Pipeline behavior:

- the automatic full pipeline does not run performance analysis because it requires real post-publish metrics
- the pipeline stage is a deliberate no-op in the auto path

## Full Pipeline Command

The all-in-one command is:

```bash
cc-deep-research content-gen pipeline --theme "founder-led growth"
```

Options:

- `--theme`
- `--idea`
- `--from-stage`
- `--to-stage`
- `--from-file`
- `-o/--output`
- `--save-context`
- `--quiet`

What it actually does today:

1. Creates a fresh `PipelineContext`.
2. Runs handlers from `from_stage` through `to_stage`.
3. Prints a summary.
4. Optionally writes:
   - final script to `--output`
   - full context to `--output.context.json` or `pipeline_context.json`

Recommended usage:

- use it to generate a first-pass pipeline context
- inspect and save that context
- handle QC approval and publish scheduling with explicit follow-up commands

## Recommended Operator Workflow

If you want the most reliable current workflow, use the modular commands with saved files.

### Option A: Full but controlled workflow

```bash
cc-deep-research content-gen strategy init
cc-deep-research content-gen strategy set niche "B2B SaaS"
cc-deep-research content-gen backlog build --theme "activation" -o backlog.json
cc-deep-research content-gen backlog score --from-file backlog.json -o scoring.json
cc-deep-research content-gen angle generate --idea "..." --audience "..." --problem "..." -o angles.json
cc-deep-research content-gen research --idea "..." --angle "..." -o research.json
cc-deep-research content-gen script --idea "..." -o script.txt --save-context
cc-deep-research content-gen visual --from-file script.txt.context.json -o visual.json
cc-deep-research content-gen production --from-file visual.json -o production.json
cc-deep-research content-gen package --from-file script.txt.context.json -o packaging.json
cc-deep-research content-gen publish schedule --from-file packaging.json --idea-id idea123
```

### Option B: Faster orchestration pass

```bash
cc-deep-research content-gen pipeline --theme "activation" -o pipeline_script.txt --save-context
cc-deep-research content-gen qc review --from-file pipeline_script.txt.context.json
cc-deep-research content-gen qc approve --idea-id idea123 --from-file pipeline_script.txt.context.json
cc-deep-research content-gen package --from-file pipeline_script.txt.context.json -o packaging.json
cc-deep-research content-gen publish schedule --from-file packaging.json --idea-id idea123
```

This second option is convenient, but it is not a true one-command publish flow yet.

## Persistence And Artifacts

Default persisted files:

- strategy memory: `~/.config/cc-deep-research/strategy.yaml`
- scripting runs: `~/.config/cc-deep-research/scripts/`
- publish queue: `~/.config/cc-deep-research/publish_queue.yaml`

Optional operator-managed files:

- backlog JSON
- scoring JSON
- angle JSON
- research-pack JSON
- visual-plan JSON
- production JSON
- packaging JSON
- performance JSON
- pipeline context JSON
- script context JSON

Storage classes exist for:

- strategy
- backlog
- scripting runs
- publish queue

Only strategy, scripting autosave, and publish-queue persistence are wired into normal CLI behavior today.

## Configuration

Content-generation settings live in [`ContentGenConfig`](../src/cc_deep_research/config/schema.py):

- `strategy_path`
- `backlog_path`
- `publish_queue_path`
- `default_platforms`
- `research_max_queries`
- `scoring_threshold_produce`

What is currently honored in code:

- `default_platforms`
- `research_max_queries`
- `scoring_threshold_produce`

What exists in the schema but is not currently wired into the storage layer:

- `strategy_path`
- `backlog_path`
- `publish_queue_path`

## LLM Routing Behavior

Each content agent uses `LLMRouteRegistry` and `LLMRouter` just like the research subsystem.

Important routing facts:

- content-generation agent IDs are not given custom route defaults in `LLMConfig.get_route_for_agent`
- in practice they fall back to the global default route
- the router can fall back across configured transports
- if no usable transport exists, the router returns an empty heuristic response

Operational consequence:

- the scripting agent checks availability first and raises a clear error if no route is available
- most other content agents do not do that check, so a missing LLM route can surface as blank outputs rather than a loud failure

## Test Coverage

The main automated coverage is in [`tests/test_content_gen.py`](../tests/test_content_gen.py). The tests focus on:

- model defaults
- store round-trips
- CLI wiring
- parsing behavior for scripting
- pipeline stage count and some guardrails

This is useful regression coverage, but it is not a full live integration suite for every agent against every provider.

## Current Gaps And Caveats

The implementation is usable, but several parts are still transitional.

### `pipeline --from-file` is currently ignored

The CLI exposes `--from-file`, but the parameter is not used by the pipeline command implementation. The command always creates a fresh `PipelineContext`.

Practical impact:

- you cannot truly resume the full pipeline from a saved pipeline context
- any workflow that expects `qc approve` plus `pipeline --from-file --from-stage 10` will not work as advertised

### `pipeline --idea` does not skip backlog

The help text says `--idea` should skip backlog and start scripting with that idea. The current implementation only uses `theme or idea or "general"` as the theme argument to `run_full_pipeline`.

Practical impact:

- `--idea` behaves like an alternate theme string, not a direct scripting seed

### Starting from a later stage only works if prior state exists, but the CLI does not load prior state

`run_full_pipeline` accepts `from_stage`, but because the CLI always starts from a new empty context, later-stage resumes are mostly useful only from code, not from the current CLI.

### Full pipeline auto-selection is narrow

The pipeline:

- chooses the first `produce_now` idea
- chooses the selected angle if present, otherwise the first angle
- does not fan out across multiple shortlisted ideas

This keeps the implementation simple, but it is closer to a single-lane prototype than a queue-driven editorial planner.

### The auto pipeline stops before publish in normal use

The QC stage always produces `approved_for_publish = False`. The publish stage only runs if approval is already `True`.

Because the current pipeline command does not reload saved context, the normal all-in-one flow does not reach stage 10 automatically.

### Backlog persistence is incomplete

`BacklogStore` exists, but `content-gen backlog build` and `content-gen backlog score` do not automatically write to it. Backlog outputs are file-based unless you save them explicitly and manage persistence yourself.

### Path configuration is incomplete

The config schema includes storage path overrides, but the storage classes still default directly to XDG-style paths under `~/.config/cc-deep-research/`.

### Publish-item context storage is lossy

`PublishAgent.schedule()` returns a list of publish items, one per platform. The full pipeline keeps only the first one in `PipelineContext.publish_item`.

### Research-pack query templates are partly hard-coded

The search-query builder uses a fixed set of heuristics, including one year-specific query string that still references `2025`.

## Extension Opportunities

The most obvious next improvements are:

1. Make `pipeline --from-file` actually load and resume `PipelineContext`.
2. Make `pipeline --idea` bypass backlog and seed scripting directly.
3. Wire config path overrides into `StrategyStore`, `BacklogStore`, and `PublishQueueStore`.
4. Persist backlog outputs automatically when operators request a managed workflow.
5. Add stricter validation to non-scripting agents when LLM output is empty or malformed.
6. Expand the pipeline context to retain all publish items, not only the first.
7. Replace stale year-pinned research queries with relative or current-year logic.

## Source Map

Primary implementation files:

- orchestrator: [`src/cc_deep_research/content_gen/orchestrator.py`](../src/cc_deep_research/content_gen/orchestrator.py)
- CLI: [`src/cc_deep_research/content_gen/cli.py`](../src/cc_deep_research/content_gen/cli.py)
- models: [`src/cc_deep_research/content_gen/models.py`](../src/cc_deep_research/content_gen/models.py)
- agents: [`src/cc_deep_research/content_gen/agents/`](../src/cc_deep_research/content_gen/agents/)
- prompts: [`src/cc_deep_research/content_gen/prompts/`](../src/cc_deep_research/content_gen/prompts/)
- storage: [`src/cc_deep_research/content_gen/storage/`](../src/cc_deep_research/content_gen/storage/)
- tests: [`tests/test_content_gen.py`](../tests/test_content_gen.py)

If you are changing workflow behavior, update the prompts, parsers, CLI contract, and this document together. They are tightly coupled.
