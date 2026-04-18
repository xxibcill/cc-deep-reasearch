# Beat Structure Guide

This document explains how beat structure works in the current content-generation system.

It is intended to answer four questions:

1. What a "beat" means in this codebase
2. Where beats are created and stored
3. How beats constrain script generation and revision
4. How beats flow into visual planning, QC, and dashboard observability

The goal here is to describe the current shipped implementation, not a future idealized workflow.

## Short Answer

A beat is the smallest named narrative unit that the system plans explicitly and then tries to preserve through the rest of the pipeline. Beats are first grounded in the argument map as claim-and-proof-backed narrative moves, then carried into scripting as a `ScriptStructure` plus a `BeatIntentMap`, then preserved across drafting, retention revision, tightening, QC, targeted repairs, and visual translation.

In the standalone scripting workflow, the model chooses a structure template and defines beat intents itself. In the full pipeline, beats usually come from the upstream argument map, which means the structure is already tied to safe claims, proof anchors, counterarguments, and transitions before drafting begins.

## Core Definitions

### Beat

A beat is one named step in the script's narrative progression. In this repository, a beat is not just a paragraph break or timing chunk. It is an explicit planning unit with a purpose.

A beat can carry:

- a beat name such as `Hook`, `Problem`, `What's True`, or `CTA`
- a goal or intent
- linked claim IDs
- linked proof anchor IDs
- linked counterargument IDs
- a transition note to the next beat

### Beat Structure

Beat structure is the ordered list of beats that defines the script's narrative skeleton. In code this is primarily represented by `ScriptStructure.beat_list`.

The structure answers:

- what the beats are called
- what order they appear in
- how many beats exist

### Beat Intent

Beat intent is the operational purpose of a beat. It answers what the beat must accomplish, not how the final line should sound.

Examples:

- challenge the default assumption quickly
- surface a proof point before the viewer loses interest
- frame the better approach in concrete language
- land a specific payoff for the audience

### Beat Claim Plan

The beat claim plan is the evidence-backed narrative plan produced by the argument map stage. It ties each beat to approved claims and proof anchors before scripting starts.

This is represented by `ArgumentMap.beat_claim_plan`, where each `ArgumentBeatClaim` includes:

- `beat_id`
- `beat_name`
- `goal`
- `claim_ids`
- `proof_anchor_ids`
- `counterargument_ids`
- `transition_note`

### Stable Beat and Weak Beat

During iterative QC, beats can be classified as:

- stable: passed QC and should be preserved unchanged
- weak: requires repair because of unsupported claims, stale evidence, or poor narrative performance

This classification lives in `TargetedRevisionPlan`.

## Beat List Overview

If you just want a quick overview of the beat lists the system uses, split them into two buckets:

- full-pipeline beat lists, which are dynamic and usually come from `ArgumentMap.beat_claim_plan`
- standalone scripting beat lists, which come from the current prompt template library

### Full Pipeline: Dynamic Beat Lists

In the full content pipeline, the beat list is usually seeded from upstream planning rather than chosen from a fixed template.

The source of truth is:

- `ArgumentMap.beat_claim_plan`
- then `ScriptStructure.beat_list = [beat.beat_name for beat in argument_map.beat_claim_plan]`

That means the beat names can vary by topic. A representative seeded beat list looks like:

- Hook
- Reframe
- Proof
- Close

### Standalone Scripting: Current Template Beat Lists

The current standalone prompt library in [`src/cc_deep_research/content_gen/prompts/scripting.py`](../src/cc_deep_research/content_gen/prompts/scripting.py) defines these beat lists:

| Template | Beat list |
| --- | --- |
| `Insight Breakdown` | `Hook` -> `Why this matters` -> `Point 1` -> `Point 2` -> `Point 3` -> `Core takeaway` -> `CTA` |
| `Mistake to Fix` | `Hook` -> `Pain point` -> `What most people do wrong` -> `What to do instead` -> `Why it works` -> `Expected result` -> `CTA` |
| `Story-Based` | `Hook` -> `Starting situation` -> `Conflict / struggle` -> `Turning point` -> `Lesson` -> `Payoff / result` -> `CTA` |
| `Myth vs Truth` | `Hook` -> `The popular belief` -> `Why people believe it` -> `Why it breaks down` -> `What's actually true` -> `What to do with that truth` -> `CTA` |
| `Tutorial / How-To` | `Hook` -> `Desired outcome` -> `Step 1` -> `Step 2` -> `Step 3` -> `Common pitfall` -> `CTA` |
| `Result-First / Case Study` | `Hook with result` -> `Context` -> `What changed` -> `Why it worked` -> `Lesson` -> `CTA` |
| `Opinion / Hot Take` | `Hook` -> `Bold claim` -> `Why most people disagree` -> `Your reasoning` -> `Implication` -> `CTA` |
| `Before vs After` | `Hook` -> `Before` -> `What changed` -> `After` -> `Lesson` -> `CTA` |

For implementation details, the prompt library is the current source of truth. The docs may sometimes summarize a smaller subset of these structures at a higher level.

## Where Beats Live

Beat-related state exists in several artifacts, each with a different purpose.

| Artifact | Model | Purpose |
| --- | --- | --- |
| Argument map | `ArgumentBeatClaim` inside `ArgumentMap.beat_claim_plan` | Grounded beat planning tied to claims and proof |
| Script structure | `ScriptStructure` | Ordered beat list and structure name |
| Beat intents | `BeatIntentMap` | What each beat must accomplish |
| Visual notes | `VisualNote` | Inline production note attached to a beat |
| Targeted revision | `BeatRevisionScope` | Marks stable and weak beats for surgical repair |
| Scripting trace | `ScriptingStepTrace` | Records parsed outputs and raw LLM calls for beat-related steps |

Primary source files:

- [`src/cc_deep_research/content_gen/models.py`](../src/cc_deep_research/content_gen/models.py)
- [`src/cc_deep_research/content_gen/prompts/scripting.py`](../src/cc_deep_research/content_gen/prompts/scripting.py)
- [`src/cc_deep_research/content_gen/prompts/argument_map.py`](../src/cc_deep_research/content_gen/prompts/argument_map.py)
- [`src/cc_deep_research/content_gen/prompts/visual.py`](../src/cc_deep_research/content_gen/prompts/visual.py)
- [`src/cc_deep_research/content_gen/orchestrator.py`](../src/cc_deep_research/content_gen/orchestrator.py)

## Data Model Reference

### `ScriptStructure`

Defined in [`models.py`](../src/cc_deep_research/content_gen/models.py).

Fields:

- `chosen_structure`: human-readable structure label
- `why_it_fits`: rationale for the structure choice
- `beat_list`: ordered list of beat names

This is the canonical structure container used by scripting and visual translation.

### `BeatIntent`

Fields:

- `beat_id`
- `beat_name`
- `intent`
- `claim_ids`
- `proof_anchor_ids`
- `counterargument_ids`
- `transition_note`

This is the most operational beat object in scripting. It is where narrative purpose and evidence grounding meet.

### `BeatIntentMap`

Fields:

- `beats`: list of `BeatIntent`

This is the step-4 output of the scripting pipeline.

### `ArgumentBeatClaim`

Fields:

- `beat_id`
- `beat_name`
- `goal`
- `claim_ids`
- `proof_anchor_ids`
- `counterargument_ids`
- `transition_note`

This is the upstream, evidence-grounded beat planning object created before script wording exists.

### `VisualNote`

Fields:

- `beat_name`
- `line`
- `note`

This attaches production-oriented annotations to spoken lines in step 9 of scripting.

### `BeatRevisionScope`

Fields:

- `beat_id`
- `beat_name`
- `weak_claim_ids`
- `missing_proof_ids`
- `weakness_reason`
- `is_stable`

This is how the QC loop reasons about whether a beat should be preserved or repaired.

### `TargetedRevisionPlan`

Fields:

- `stable_beats`
- `weak_beats`
- `actions`
- `revision_summary`
- `full_restart_recommended`
- `is_patch`
- `retrieval_gaps`

This is the mechanism that enables beat-level repairs instead of full-script rewrites.

## Beat Lifecycle Across the Pipeline

### 1. Beats Are Planned in the Argument Map

The full content pipeline creates beats first in stage 6, the argument map builder.

The argument map prompt explicitly requires a `beat_claim_plan` that maps narrative beats to claims and proof IDs. This is the first point where the system treats beats as evidence-bearing units rather than just writing structure.

What gets decided here:

- the beat names
- the beat goals
- which claims each beat is allowed to carry
- which proof anchors support those claims
- which counterarguments belong in which beat
- how the script should transition forward

Why this matters:

- scripting inherits a grounded narrative plan instead of improvising unsupported lines
- QC can later reason about weak beats at the claim level
- visual planning can later map each beat to a visual treatment

### 2. Beats Seed the Scripting Context

The orchestrator has two helper functions:

- `_seed_structure_from_argument_map()`
- `_seed_beat_intents_from_argument_map()`

These translate `ArgumentMap.beat_claim_plan` into:

- `ScriptStructure`
- `BeatIntentMap`

The seeded structure uses:

- `chosen_structure = "Argument map guided flow"`
- `why_it_fits = "Derived directly from the evidence-backed beat claim plan."`
- `beat_list = [beat.beat_name for beat in argument_map.beat_claim_plan]`

The seeded beat intents copy across:

- beat ID
- beat name
- goal as `intent`
- claim IDs
- proof anchor IDs
- counterargument IDs
- transition note

This is the key bridge from research-backed planning into script writing.

### 3. Full Pipeline Usually Skips Directly to Hooks

In the full content pipeline, if both seeded `structure` and seeded `beat_intents` exist, scripting starts at step 5 rather than rebuilding them.

Current behavior:

- if both structure and beat intents are present, `start_step = 5`
- otherwise, `start_step = 3`

That means the full pipeline usually does not ask the LLM to re-choose beat structure. It uses the upstream beat plan as authoritative input and moves on to:

- hook generation
- draft writing
- retention revision
- tightening
- visual notes
- QC

This is an important difference from the standalone scripting mode.

### 4. Standalone Scripting Can Create Beats From Scratch

The standalone scripting workflow is a 10-step sub-pipeline:

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

In this mode, the LLM itself chooses a structure template and then defines a beat intent map. The current standalone prompt library includes these template families:

- `Insight Breakdown`
- `Mistake to Fix`
- `Story-Based`
- `Myth vs Truth`
- `Tutorial / How-To`
- `Result-First / Case Study`
- `Opinion / Hot Take`
- `Before vs After`

These templates define the beat sequence the rest of the scripting process must preserve. For the exact beat lists, see [Beat List Overview](#beat-list-overview).

### 5. Beats Constrain Drafting

During step 6, `draft_script`, the prompt enforces several hard beat-related rules.

The draft must:

- follow the chosen structure
- keep the exact same beat order
- keep the exact same beat count
- keep the exact same beat labels
- use beat intents exactly
- avoid adding, removing, merging, splitting, or renaming beats
- use the argument map and beat-level claim/proof links as the source of truth

The draft prompt also makes early beats do extra work:

- the first two beats must do the heaviest retention work
- the second beat must quickly add tension, pain, proof, or surprise

This means beats are not loose editorial suggestions. They are hard constraints on the script's narrative skeleton.

### 6. Beats Constrain Revision and Tightening

Steps 7 and 8 preserve beat integrity while changing the wording.

Retention revision rules include:

- preserve exact beat order, count, and labels
- do not add, remove, merge, split, or rename beats while revising
- tighten the first two beats before touching anything else
- move proof or example earlier if payoff feels delayed

Tightening rules include:

- keep the first two beats sharp and fast
- preserve exact beat order, count, and labels
- do not add, remove, merge, split, or rename beats during tightening

So the system treats beats as stable narrative scaffolding even when the script is being rewritten for performance.

### 7. Beats Flow Into Visual Translation

The visual translation stage requires:

- a script version
- a beat list from `ScriptStructure`

For each beat, the visual prompt asks for:

- spoken line
- visual treatment
- shot type
- A-roll
- B-roll
- on-screen text
- overlay or graphic
- prop or asset
- transition
- retention function

The visual prompt also requires:

- a meaningful visual change every 1-3 beats
- a trailing `visual_refresh_check`

This means the beat list is not only a writing structure. It is also the primary coordination surface between script logic and production planning.

### 8. Beats Participate in QC and Iterative Repair

When the quality evaluator finds localized problems, it can produce a `TargetedRevisionPlan` instead of forcing a full restart.

This plan identifies:

- stable beats that should remain untouched
- weak beats that need repair
- repair actions for specific beats or claims
- retrieval gaps for missing evidence

The targeted revision mode is intentionally beat-scoped:

- targeted research can run for weak beats' evidence gaps
- stable beats are marked for preservation
- scripting receives feedback telling it which beats must stay unchanged

This is one of the strongest reasons beats exist as explicit objects in the system. They let the pipeline repair only the broken parts.

## Beat Invariants and Guardrails

The following invariants show up repeatedly in prompts and orchestration logic.

### 1. Beat identity is meant to be stable

Once structure is chosen or seeded, later steps should not:

- add beats
- remove beats
- merge beats
- split beats
- rename beats
- reorder beats

### 2. Early beats carry disproportionate importance

The system repeatedly emphasizes the first two beats because they determine viewer retention:

- they must earn attention quickly
- they should surface pain, contrast, surprise, proof, or tension early
- they are tightened first during revision

### 3. Beats must remain grounded in supported claims

If an argument map is present:

- beats should map only to safe claims
- proof anchors must support those claims
- unsafe claims must not be treated as settled fact
- research context is fallback, not a reason to exceed the supported claim set

### 4. Beat structure is separate from final line wording

Beat names and intents are operational planning labels. They are not necessarily the same as the spoken line in the final script.

For example:

- beat name: `Why It Fails`
- intent: expose the hidden downside of the default behavior
- spoken line: a concise, natural sentence that delivers that point

### 5. Beats connect writing and production

Each beat eventually becomes:

- one narrative move in the script
- one unit of visual planning
- one possible target for revision or evidence repair
- one countable unit in metadata and observability

## High-Level Template Library

The current standalone prompt library defines eight beat-template families.

### `Insight Breakdown`

Beat sequence:

- Hook
- Why this matters
- Point 1
- Point 2
- Point 3
- Core takeaway
- CTA

Best suited for:

- expert explanation
- structured educational content
- multi-part breakdowns

Risk:

- can become slow if proof or contrast arrives too late

### `Mistake to Fix`

Beat sequence:

- Hook
- Pain point
- What most people do wrong
- What to do instead
- Why it works
- Expected result
- CTA

Best suited for:

- correction-oriented content
- practical advice
- reframing bad defaults into better actions

Risk:

- can feel generic if the mistake is obvious or the fix is vague

### `Story-Based`

Beat sequence:

- Hook
- Starting situation
- Conflict / struggle
- Turning point
- Lesson
- Payoff / result
- CTA

Best suited for:

- experiential examples
- founder or operator stories
- one clear lesson with emotional movement

Risk:

- can waste early seconds on setup if the turning point is delayed

### `Myth vs Truth`

Beat sequence:

- Hook
- The popular belief
- Why people believe it
- Why it breaks down
- What's actually true
- What to do with that truth
- CTA

Best suited for:

- contrarian education
- audience-belief reversal
- mechanism-based reframing

Risk:

- fails if the myth is weak or the truth is not more useful than the myth

### `Tutorial / How-To`

Beat sequence:

- Hook
- Desired outcome
- Step 1
- Step 2
- Step 3
- Common pitfall
- CTA

Best suited for:

- process explanation
- tactical teaching
- stepwise implementation

Risk:

- can become generic if the steps are obvious or interchangeable

### `Result-First / Case Study`

Beat sequence:

- Hook with result
- Context
- What changed
- Why it worked
- Lesson
- CTA

Best suited for:

- outcome-led examples
- credibility-building proof
- showing a change in practice

Risk:

- can feel unearned if the result arrives before enough context or proof

### `Opinion / Hot Take`

Beat sequence:

- Hook
- Bold claim
- Why most people disagree
- Your reasoning
- Implication
- CTA

Best suited for:

- strong point-of-view content
- expert disagreement
- concise argumentative pieces

Risk:

- falls apart if the disagreement is overstated or the reasoning is thin

### `Before vs After`

Beat sequence:

- Hook
- Before
- What changed
- After
- Lesson
- CTA

Best suited for:

- transformation-focused content
- process improvement examples
- simple contrast-driven storytelling

Risk:

- can feel shallow if the change is asserted without a clear mechanism

## Full Pipeline vs Standalone Scripting

| Aspect | Standalone scripting | Full pipeline |
| --- | --- | --- |
| Beat source | LLM chooses structure and intents in steps 3 and 4 | Upstream argument map usually seeds both |
| Start point | Step 1 | Usually step 5 if seeding succeeded |
| Evidence grounding | Optional unless research and argument context are supplied | Native, because beats come from `beat_claim_plan` |
| Structure label | Template name such as `Myth vs Truth` | Usually `Argument map guided flow` |
| Repair strategy | Can revise whole script | Can preserve stable beats and repair weak beats selectively |

The important practical takeaway is that the full pipeline treats beats less like a creative writing aid and more like a controlled execution plan.

## Example Beat Flow

This example shows the same beat as it moves through the system.

```text
ArgumentMap.beat_claim_plan
  beat_id: beat_1
  beat_name: Common Belief
  goal: Name the default belief the audience currently trusts
  claim_ids: claim_3
  proof_anchor_ids:
  counterargument_ids:
  transition_note: Move quickly into why that belief breaks down

-> seeded into BeatIntentMap
  beat_id: beat_1
  beat_name: Common Belief
  intent: Name the default belief the audience currently trusts
  claim_ids: claim_3
  proof_anchor_ids:
  counterargument_ids:
  transition_note: Move quickly into why that belief breaks down

-> used in script drafting
  [Common Belief]: Most teams think more features automatically mean better retention.

-> used in visual planning
  beat: Common Belief
  spoken_line: Most teams think more features automatically mean better retention.
  visual: crowded product UI with too many highlighted elements
```

## Beat Traceability and Observability

Beats are visible in several operator-facing surfaces.

### Scripting step traces

`ScriptingContext.step_traces` records structured outputs and LLM calls for each scripting step, including:

- `choose_structure`
- `define_beat_intents`
- later steps that consume beat plans

Each trace can contain:

- step name
- step label
- iteration number
- raw prompts
- raw responses
- parsed output

This is the most detailed debugging view for beat generation and beat drift.

### Dashboard

The dashboard's `Run Scripting` panel surfaces:

- beat structure
- tone
- CTA
- angle
- hooks
- final word count
- final script
- full scripting trace with prompts and raw responses

This is the main operator UI for inspecting how a beat plan turned into a final script.

### Stage metadata

The pipeline also records beat counts in metadata so operators can quickly see:

- how many beats exist in the argument map
- how many beat-level visuals were created

### Saved scripting runs

Standalone scripting runs are autosaved, including context artifacts that preserve beat state. Relevant commands are documented in [`docs/content-generation.md`](./content-generation.md).

Examples:

```bash
cc-deep-research content-gen script --idea "..." -o script.txt --save-context
cc-deep-research content-gen script --from-file script.context.json --from-step 6
cc-deep-research content-gen scripts list
cc-deep-research content-gen scripts show --latest
```

Autosaved outputs include:

- `~/.config/cc-deep-research/scripts/latest.txt`
- `~/.config/cc-deep-research/scripts/latest.context.json`
- `~/.config/cc-deep-research/scripts/latest.json`

## Relationship to Claim Safety

Beats matter for factual safety because claims are not only tracked globally. They are mapped to specific beats.

That enables the system to answer questions like:

- which beat introduced this claim
- which proof anchors justify that line
- whether a weak claim is isolated to one beat or spread across the script
- whether a revision can patch one beat instead of restarting the whole script

This beat-level grounding is one of the main safety boundaries between research and copy generation.

## Relationship to Visual and Production Planning

Beats are the handoff point between writing and making the asset.

After scripting:

- visual translation expands each beat into a visual treatment
- production planning turns those treatments into setup, prop, and execution requirements

Without explicit beats, the handoff from text to production would be much less reliable because the system would have no stable narrative units to map onto shots and transitions.

## Current Caveats

### 1. `docs/scripting.md` is a high-level template guide, not the whole beat system

It documents the generic standalone structure templates, but the production pipeline goes further by grounding beats in the argument map and targeted revision system.

### 2. Full-pipeline beats are often more authoritative than template beats

When the orchestrator seeds structure and beat intents from `beat_claim_plan`, those beats are derived from evidence-backed planning rather than selected from a generic template family.

### 3. Beat preservation is a design goal, not a mathematical guarantee

Prompts and orchestration strongly enforce beat stability, but final compliance still depends on LLM behavior and parser recovery. That is why traces, QC, and targeted revision exist.

### 4. Beat names are meaningful API surface

Because later stages key off beat names and IDs, careless renaming can break continuity between:

- argument map
- beat intents
- visual notes
- visual plan
- targeted revision

## Related Documents

- [`docs/scripting.md`](./scripting.md)
- [`docs/scripting-pipeline-schemas.md`](./scripting-pipeline-schemas.md)
- [`docs/content-generation.md`](./content-generation.md)
- [`docs/content-gen-workflow-template.md`](./content-gen-workflow-template.md)
- [`docs/DASHBOARD_GUIDE.md`](./DASHBOARD_GUIDE.md)
- [`docs/content-gen-artifact.md`](./content-gen-artifact.md)

## Source Files Worth Reading

- [`src/cc_deep_research/content_gen/models.py`](../src/cc_deep_research/content_gen/models.py)
- [`src/cc_deep_research/content_gen/agents/scripting.py`](../src/cc_deep_research/content_gen/agents/scripting.py)
- [`src/cc_deep_research/content_gen/prompts/scripting.py`](../src/cc_deep_research/content_gen/prompts/scripting.py)
- [`src/cc_deep_research/content_gen/prompts/argument_map.py`](../src/cc_deep_research/content_gen/prompts/argument_map.py)
- [`src/cc_deep_research/content_gen/prompts/quality_evaluator.py`](../src/cc_deep_research/content_gen/prompts/quality_evaluator.py)
- [`src/cc_deep_research/content_gen/prompts/visual.py`](../src/cc_deep_research/content_gen/prompts/visual.py)
- [`src/cc_deep_research/content_gen/orchestrator.py`](../src/cc_deep_research/content_gen/orchestrator.py)
