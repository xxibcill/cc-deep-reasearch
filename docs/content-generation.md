# Content-Generation Workflow

This document describes the full content-generation system as it is currently implemented in `cc-deep-research`. It covers the architecture, the stage-by-stage flow, the CLI entrypoints, the saved artifacts, and the places where the intended product workflow is ahead of the shipped code.

## Contract Versioning

The canonical inventory for prompt-output contracts lives in
[`CONTENT_GEN_STAGE_CONTRACTS`](../src/cc_deep_research/content_gen/models.py) in
[`src/cc_deep_research/content_gen/models.py`](../src/cc_deep_research/content_gen/models.py).
Each prompt-backed stage also carries a prompt-module `CONTRACT_VERSION`.

Each contract includes:
- A `CONTRACT_VERSION` constant (e.g., "1.0.0")
- Parser expectations documented in the prompt module docstring
- A shared registry entry naming the parser location, output model, expected sections, and failure mode
- Expected output format for LLM responses

When editing prompts, update the prompt docstring and the shared registry together so the parser remains compatible:

| Stage | Prompt Module | Contract Version | Failure Mode |
|-------|--------------|------------------|--------------|
| Opportunity planning | `prompts/opportunity.py` | 1.0.0 | fail-fast |
| Backlog build | `prompts/backlog.py` | 1.0.0 | tolerant/degraded |
| Idea scoring | `prompts/backlog.py` | 1.0.0 | tolerant/degraded |
| Angle generation | `prompts/angle.py` | 1.0.0 | fail-fast |
| Research pack | `prompts/research_pack.py` | 1.1.0 | tolerant |
| Argument map | `prompts/argument_map.py` | 1.0.0 | fail-fast |
| Scripting (all 10 steps) | `prompts/scripting.py` | 1.1.0 | mostly fail-fast |
| Visual translation | `prompts/visual.py` | 1.0.0 | fail-fast |
| Production brief | `prompts/production.py` | 1.0.0 | tolerant |
| Packaging | `prompts/packaging.py` | 1.0.0 | fail-fast |
| QC review | `prompts/qc.py` | 1.1.0 | human-gated |
| Publish queue | `prompts/publish.py` | 1.0.0 | tolerant |
| Performance analysis | `prompts/performance.py` | 1.0.0 | tolerant |
| Shared registry/models | `models.py` | 1.3.0 | n/a |

The models in `models.py` define the Python types that result from parsing LLM output. Major changes to prompt output formats should be accompanied by:
1. Bumping the `CONTRACT_VERSION` in the prompt module
2. Updating `CONTENT_GEN_STAGE_CONTRACTS` in `models.py`
3. Updating the parser in the corresponding agent
4. Verifying tests pass with `uv run pytest tests/test_content_gen.py tests/test_iterative_loop.py -v`

## Scope

The content-generation subsystem is separate from the research-report pipeline. It lives under [`src/cc_deep_research/content_gen/`](../src/cc_deep_research/content_gen/) and is focused on short-form video creation:

- persistent strategy memory
- opportunity brief planning
- idea backlog generation and scoring
- angle development
- compact research-pack synthesis
- argument-map planning
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
- the canonical contract inventory is `CONTENT_GEN_STAGE_CONTRACTS` in `models.py`
- most stages depend on delimiter blocks like `---` and `field_name: value`
- if prompt wording changes, the parser may also need to change
- empty or malformed LLM output can degrade into partial or blank models

The scripting agent is the strictest implementation. It validates missing fields aggressively and raises `ValueError` when required outputs are absent. Most other agents are more permissive and will often return sparse models instead of failing fast.

## Main Data Models

The workflow revolves around two context objects:

- [`PipelineContext`](../src/cc_deep_research/content_gen/models.py)
  The top-level 14-stage pipeline state.
- [`ScriptingContext`](../src/cc_deep_research/content_gen/models.py)
  The nested 10-step script-generation state machine.

Important stage models:

- `StrategyMemory`
- `OpportunityBrief`
- `BacklogOutput` and `BacklogItem`
- `ScoringOutput` and `IdeaScores`
- `AngleOutput` and `AngleOption`
- `ResearchPack`
- `ArgumentMap`
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

Run the 14-stage orchestrated flow:

```bash
cc-deep-research content-gen pipeline --theme "..."
```

This path works for generation up through QC, with the remaining operational caveats documented below in [Current Gaps And Caveats](#current-gaps-and-caveats).

## End-To-End Flow

The implemented pipeline order is defined by `PIPELINE_STAGES` in [`src/cc_deep_research/content_gen/models.py`](../src/cc_deep_research/content_gen/models.py):

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

Operationally, the flow looks like this:

```text
strategy memory
  -> opportunity brief
  -> backlog ideas
  -> scored shortlist
  -> top-2 candidate queue
  -> one primary execution lane
  -> multiple angles
  -> one chosen angle
  -> research pack
  -> argument map
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

### Stage 1: Opportunity Planning

Implementation:

- agent: [`OpportunityPlanningAgent`](../src/cc_deep_research/content_gen/agents/opportunity.py)
- prompt: [`prompts/opportunity.py`](../src/cc_deep_research/content_gen/prompts/opportunity.py)
- output model: `OpportunityBrief`

Purpose:

- turn a raw theme into a structured editorial contract
- define audience segments, problem statements, proof requirements, and success criteria
- provide sub-angles and research hypotheses to guide backlog generation and scoring

Input sources:

- theme
- strategy memory

Output fields:

- `theme`, `goal`, `primary_audience_segment`, `secondary_audience_segments`
- `problem_statements`, `content_objective`, `proof_requirements`
- `platform_constraints`, `risk_constraints`, `freshness_rationale`
- `sub_angles`, `research_hypotheses`, `success_criteria`

Pipeline behavior:

- runs after strategy load and before backlog generation
- the backlog builder can read the brief for richer context, though it does not require every field

### Stage 2: Backlog Builder

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

### Stage 3: Idea Scoring

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

- scoring returns a ranked `shortlist`, `selected_idea_id`, `selection_reasoning`, `runner_up_idea_ids`, and a small `active_candidates` queue
- the full pipeline keeps the top 2 ideas alive as `active_candidates`: one `primary` lane and one `runner_up`
- downstream execution still advances the primary lane, but the runner-up remains explicit in `PipelineContext` and backlog status

### Stage 4: Angle Generation

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
- angle parsing is now fail-fast for blank or incomplete options; at least one option must include
  `target_audience`, `viewer_problem`, `core_promise`, and `primary_takeaway`

### Stage 5: Research Pack Builder

Implementation:

- agent: [`ResearchPackAgent`](../src/cc_deep_research/content_gen/agents/research_pack.py)
- prompt: [`prompts/research_pack.py`](../src/cc_deep_research/content_gen/prompts/research_pack.py)
- output model: `ResearchPack`

Purpose:

- produce enough evidence to support the content without drifting into open-ended research

How it works:

1. Build a small, purpose-driven query-family set from the idea and angle.
2. Run those queries through the configured search providers.
3. Convert snippets into a compact search context string.
4. Ask the LLM to synthesize structured findings, claims, counterpoints, and risk flags.

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
- query generation is intentionally small, but the families are retrieval-oriented:
  `proof`, `primary-source`, `competitor`, `contrarian`, `freshness`, and `practitioner-language`
- freshness queries use the current calendar year instead of a stale pinned year
- supporting sources retain source-level provenance including `query`, `query_family`, `intent_tags`,
  and merged query history when duplicate URLs appear from multiple searches
- the stored research pack is compact by design and not a citation-grade source graph
- this parser is intentionally tolerant: missing sections stay empty because scripting can continue with
  partial research and iterative reruns can add missing evidence later

### Stage 6: Argument Map Builder

Implementation:

- agent: [`ArgumentMapAgent`](../src/cc_deep_research/content_gen/agents/argument_map.py)
- prompt: [`prompts/argument_map.py`](../src/cc_deep_research/content_gen/prompts/argument_map.py)
- output model: `ArgumentMap`

Purpose:

- turn the selected idea, chosen angle, and structured research pack into a grounded narrative plan
- separate safe claims from unsafe claims before drafting starts

Behavior:

- the parser is fail-fast and validates cross-references between `proof_id`, `claim_id`,
  `counterargument_id`, and `beat_id`
- each beat in `beat_claim_plan` can seed later scripting structure and beat-intent setup
- the orchestrator records proof, claim, beat, and unsafe-claim counts into stage traces

### Stage 7: Scripting Pipeline

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
  - `argument_map`
  - precomputed `core_inputs`
  - precomputed `angle`
  - `structure` seeded from the argument map when beats are available
  - `beat_intents` seeded from the argument map when beats are available
- then it resumes the scripting workflow from step `3`, which is `choose_structure`

That means the full pipeline treats the earlier backlog, angle, and research stages as the upstream planning work for the scripting engine.

### Stage 8: Visual Translation

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
- the parser also fails fast if it cannot recover at least one complete beat visual or the
  required `visual_refresh_check`

### Stage 9: Production Brief

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

### Stage 10: Packaging

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
- parsing is intentionally tolerant per block, but the stage fails if no usable platform package
  survives parsing

### Stage 11: Human QC Gate

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
- when available, QC compares the script against both research-summary and argument-map summary context
- `qc approve` mutates the saved context JSON by flipping `approved_for_publish` to `True`
- missing issue buckets are tolerated and default to empty lists, but `hook_strength` is required
  so a blank QC review does not silently pass through the pipeline

### Stage 12: Publish Queue

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
- the full pipeline now retains all generated publish items in `PipelineContext.publish_items`
- `PipelineContext.publish_item` remains as the first-item compatibility alias for older callers and saved contexts

### Stage 13: Performance Analysis

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

1. Creates a fresh `PipelineContext`, or reloads a saved one with `--from-file`.
2. Supports direct-idea bypass with `--idea`, seeding the pipeline from a selected idea instead of backlog generation.
3. Runs handlers from `from_stage` through `to_stage`.
4. Prints a summary.
5. Optionally writes:
   - final script to `--output`
   - full context to `--output.context.json` or `pipeline_context.json`

Recommended usage:

- use it to generate a first-pass pipeline context
- inspect and save that context
- resume later stages with `--from-file` when you want to continue from QC approval or another saved checkpoint
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
- browser-started pipeline jobs: `~/.config/cc-deep-research/content-gen/pipelines/`

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
- browser-started pipeline jobs

What is wired into normal workflow behavior today:

- strategy persistence
- scripting autosave
- publish-queue persistence
- browser-started pipeline job persistence and restart recovery
- CLI pipeline context checkpointing after each completed stage when a context output path is configured
- best-effort partial pipeline-context save on CLI pipeline failure

## Configuration

Content-generation settings live in [`ContentGenConfig`](../src/cc_deep_research/config/schema.py):

- `strategy_path`
- `backlog_path`
- `publish_queue_path`
- `default_platforms`
- `research_max_queries`
- `scoring_threshold_produce`

What is currently honored in code:

- `strategy_path`
- `backlog_path`
- `publish_queue_path`
- `default_platforms`
- `research_max_queries`
- `scoring_threshold_produce`

## LLM Routing Behavior

Each content agent uses `LLMRouteRegistry` and `LLMRouter` just like the research subsystem.

Important routing facts:

- content-generation agent IDs are not given custom route defaults in `LLMConfig.get_route_for_agent`
- in practice they fall back to the global default route
- the router can fall back across configured transports
- if no usable transport exists, the router ultimately falls back to an empty heuristic response internally

Operational consequence:

- the scripting agent checks availability first and raises a clear error if no route is available
- non-scripting content agents now also check route availability before execution
- non-scripting agents retry once when the router returns a blank shell
- fail-fast stages still raise on empty responses after retry
- tolerant stages keep their degraded/partial behavior, but they no longer silently continue when no usable LLM route exists

## Test Coverage

The main automated coverage is in [`tests/test_content_gen.py`](../tests/test_content_gen.py). The tests focus on:

- model defaults
- store round-trips
- CLI wiring
- contract-registry consistency
- parser behavior for research-pack, argument-map, scripting, evaluator, and QC outputs
- pipeline stage count and stage-order guardrails
- iterative quality-loop stop conditions and feedback formatting

This is useful regression coverage, but it is not a full live integration suite for every agent against every provider.

## Dashboard Operator Visibility

The dashboard pipeline detail page at `/content-gen/pipeline/[id]` is the operator-facing view for a live or completed content-generation run.

- Each pipeline stage renders its own detailed panel instead of a compact summary-only block.
- Ideation stages surface the full shortlist, scoring breakdowns, angle options, and research-pack detail already stored in `PipelineContext`.
- The scripting stage shows both the final script artifact and the full step-trace inspector, including prompts, provider/model metadata, raw responses, and parsed outputs.
- Stage traces expose structured metadata such as selected idea/angle ids, shortlist counts, proof/fact counts, cache reuse, LLM call counts, word counts, and iteration signals.
- While a run is active, websocket stage events carry the latest context snapshot so stage detail becomes visible progressively instead of waiting for terminal completion.

## Current Gaps And Caveats

The implementation is usable, but several parts are still transitional.

### Full pipeline execution is still primary-lane first

The pipeline now preserves a small top-2 candidate queue, but downstream automation still executes only the primary candidate lane in a given run.

Practical impact:

- the second candidate is preserved and visible, but it is not automatically researched and scripted in parallel
- fanout is intentionally capped at 2 ideas, not arbitrary breadth

### Publish still requires an explicit human approval pass

The QC stage always produces `approved_for_publish = False`. The publish stage only runs if approval is already `True`.

Practical impact:

- a normal all-in-one pipeline run still stops before publish
- operators should use `qc approve` and then resume the pipeline with `--from-file` when they want to continue from the saved context

### Backlog persistence is incomplete

`BacklogStore` exists, but `content-gen backlog build` and `content-gen backlog score` do not automatically write to it. Backlog outputs are file-based unless you save them explicitly and manage persistence yourself.

### CLI and browser pipeline persistence are now durable, but stage artifacts are still uneven

Browser-started pipeline runs now persist their latest job state and `PipelineContext`, and the CLI pipeline command now writes checkpoint-style context snapshots when you opt into a context output path.

Practical impact:

- dashboard pipeline runs survive app restart as resumable saved jobs
- interrupted in-flight dashboard runs reappear as failed/interrupted jobs with saved context instead of vanishing
- CLI pipeline runs can preserve the latest resumable context even if a later stage crashes
- individual stage artifacts like backlog JSON, research-pack JSON, and packaging JSON are still operator-managed unless you save them explicitly

### Research-pack query families are still intentionally narrow

The search-query builder now uses labeled retrieval families with current-year freshness logic, but it is still a small fixed plan rather than a dynamic fanout strategy.

## Extension Opportunities

The most obvious next improvements are:

1. Expand the active candidate queue beyond the current top-2 cap when broader editorial planning is needed.
2. Let the pipeline optionally run the runner-up lane through its own angle/research/script passes.
3. Persist backlog outputs automatically when operators request a managed workflow.
4. Expand tolerant-stage metadata so production, publish, and performance stages can record degraded empty-response outcomes more explicitly.
5. Expand retrieval planning beyond the fixed expert-query family set when broader fanout is needed.

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
