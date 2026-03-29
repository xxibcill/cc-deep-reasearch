## LLM-ready content workflow

### 0. Persistent strategy memory

This is not a step per video. It is the system memory.

Store:

- niche
- content pillars
- target audience segments
- tone rules
- offer / product / CTA rules
- platforms
- forbidden claims
- proof standards
- examples of past winners and losers

Without this, the AI will keep reinventing your identity every run.

### 1. Backlog builder

Goal: generate and maintain an idea pool across the 3 categories you already defined: trend-responsive, evergreen, authority-building.

Input:

- theme or content pillar
- recent audience questions/comments
- past top-performing content
- trend sources
- competitor signals

Output schema:

```yaml
idea_id:
category: trend-responsive | evergreen | authority-building
idea:
audience:
problem:
source:
why_now:
potential_hook:
content_type:
evidence:
risk_level:
priority_score:
status: backlog
```

Decision rule:

- reject ideas that are vague, unprovable, or too broad
- keep only ideas with a clear audience + clear payoff + at least one evidence source

### 2. Idea scorer

Goal: rank backlog items so the AI does not treat every idea equally.

Score each idea from 1–5 on:

- relevance to audience
- novelty
- authority fit
- ease of production
- evidence strength
- hook strength
- repurposing potential

Output:

```yaml
idea_id:
scores:
  relevance:
  novelty:
  authority_fit:
  production_ease:
  evidence_strength:
  hook_strength:
  repurposing:
total_score:
recommendation: produce_now | hold | kill
reason:
```

Hard rule:

- kill anything with weak evidence and weak hook
- produce now only if total score passes threshold

### 3. Angle generator

This is a separate stage because you were right: topic and angle are not the same thing.

Goal: turn one selected idea into 3–5 editorial angles.

Output schema:

```yaml
idea_id:
angle_options:
  - angle_id:
    target_audience:
    viewer_problem:
    core_promise:
    primary_takeaway:
    lens:
    format:
    tone:
    CTA:
    why_this_version_should_exist:
```

Selection rule:
Choose the angle with the strongest combination of:

- narrowest audience fit
- clearest promise
- highest contrast from competitor content
- easiest visual expression

### 4. Research pack builder

Your draft says research should be sufficient, not exhaustive. Correct. That should become a hard instruction.

Goal: build a compact research pack that makes the content credible and differentiated.

Subtasks:

- audience research
- competitor pattern scan
- substance research
- misinformation risk check

Output schema:

```yaml
idea_id:
angle_id:
audience_insights:
competitor_observations:
key_facts:
proof_points:
examples:
case_studies:
gaps_to_exploit:
assets_needed:
claims_requiring_verification:
unsafe_or_uncertain_claims:
research_stop_reason:
```

Stop condition:
Stop researching when all of these are true:

- you have 3–7 useful proof points
- you have identified 1–2 gaps in competitor coverage
- you can support the main promise
- you have flagged uncertain claims

This prevents infinite “research”.

### 5. Script architect

This is not “write a script”. It is “build attention flow”. Your notes are right on that.

Goal: produce a beat-based short-form script.

Output schema:

```yaml
idea_id:
angle_id:
script:
  hook:
  beat_1:
  beat_2:
  beat_3:
  beat_4:
  payoff:
  CTA:
retention_logic:
open_loops:
transitions:
estimated_duration_seconds:
lines_to_cut_if_too_long:
```

Script rules:

- first line must create curiosity, tension, surprise, or direct relevance
- every beat must do one job only
- no essay structure
- no background unless needed for comprehension
- every line must earn the next line
- if a line does not add curiosity, value, proof, or transition, cut it

### 6. Visual translation

You already identified that good shorts need visual refreshes every 1–3 beats. Keep that.

Goal: convert the script into a shooting and editing plan.

Output schema:

```yaml
idea_id:
angle_id:
visual_plan:
  - beat:
    spoken_line:
    visual:
    shot_type:
    a_roll:
    b_roll:
    on_screen_text:
    overlay_or_graphic:
    prop_or_asset:
    transition:
    retention_function:
```

Hard rule:
Every 1–3 beats, force one meaningful visual change:

- punch-in
- angle change
- cutaway
- screen recording
- text emphasis
- graphic
- result shot

Not random motion. Useful motion only. That is in your draft and it is correct.

### 7. Production brief

AI cannot film for you unless connected to tools, so its job here is planning.

Goal: make filming idiot-proof.

Output schema:

```yaml
idea_id:
shoot_brief:
  location:
  setup:
  wardrobe:
  props:
  assets_to_prepare:
  audio_checks:
  battery_checks:
  storage_checks:
  pickup_lines_to_capture:
  backup_plan:
```

This stage exists to prevent the exact failures you listed: forgotten screenshots, close-ups, screen recordings, pickup lines, room tone.

### 8. Packaging generator

Do not wait until the end to think about packaging.

Goal: generate publish-ready variants for each platform.

Output schema:

```yaml
idea_id:
platform_packages:
  - platform:
    primary_hook:
    alternate_hooks:
    cover_text:
    caption:
    keywords:
    hashtags:
    pinned_comment:
    CTA:
    version_notes:
```

Hard rule:
Generate at least 3 hooks, not 1.
Usually the hook is a bigger lever than minor script polishing.

### 9. Human QC gate

This must stay human-owned. Your draft already says that. Keep it as a non-negotiable gate.

Goal: approve or reject before publishing.

Checklist:

- hook is clear in first seconds
- no factual nonsense
- no weak wording
- captions readable
- visuals support the point
- audio is usable
- CTA is appropriate
- no brand/legal risk

Output schema:

```yaml
review_round:
hook_strength:
clarity_issues:
factual_issues:
visual_issues:
audio_issues:
caption_issues:
must_fix_items:
approved_for_publish: yes | no
```

### 10. Publish queue

Goal: treat publishing as queue management, not a one-off action.

Output schema:

```yaml
publish_item:
idea_id:
platform:
publish_datetime:
asset_version:
caption_version:
pinned_comment:
cross_post_targets:
first_30_minute_engagement_plan:
status: scheduled | published
```

### 11. Performance analyst

Goal: turn results into better future ideas.

Output schema:

```yaml
video_id:
metrics:
what_worked:
what_failed:
audience_signals:
dropoff_hypotheses:
hook_diagnosis:
lesson:
next_test:
follow_up_ideas:
backlog_updates:
```

On your A/B question: yes, but do not A/B test randomly. Test one variable at a time:

- hook
- opening visual
- caption package
- CTA
- length

If you change three things, the result is useless.

---

## The cleaner operating model

Your 12-step workflow can be compressed into 7 executable AI stages:

1. Build backlog
2. Score and select
3. Develop angle
4. Build research pack
5. Write beat-based script
6. Translate into visual + production brief
7. Generate package + review + learn

That is better for an LLM because each stage has one job and one output.

---

## What AI should own vs what human should own

### AI-owned

- backlog generation
- idea scoring
- angle generation
- competitor synthesis
- research synthesis
- scripting
- shot planning
- packaging variants
- analytics interpretation
- next-content recommendations

### Human-owned

- final truth check
- filming performance
- brand judgment
- legal/risk judgment
- final edit taste
- publish approval

If you try to hand final truth and final judgment fully to the model, you will get confident garbage eventually.

---

## The system prompt version

Paste this into your LLM as the operating instruction:

```text
You are my content operations system for short-form video.

Your job is to move one content idea through a strict pipeline:
1. backlog generation
2. idea scoring
3. angle development
4. research pack creation
5. beat-based scripting
6. visual and production planning
7. packaging generation
8. post-publish analysis

General rules:
- Do not skip stages.
- Do not produce vague ideas.
- Do not write essay-style scripts.
- Script in beats, not paragraphs.
- Keep research sufficient, not exhaustive.
- Separate topic from angle.
- Prefer clarity, specificity, and retention over completeness.
- Flag uncertain claims explicitly.
- Never invent facts, examples, or proof.
- When evidence is weak, say so.
- Every output must follow the requested schema exactly.
- If an idea is weak, recommend killing it rather than forcing it.

Backlog categories:
- trend-responsive
- evergreen
- authority-building

For every selected idea, use this angle formula:
We are making a video for [audience] about [topic], framed as [angle], so they can [outcome].

For scripts:
- first seconds matter most
- every beat must earn the next beat
- every line must create curiosity, deliver value, prove a point, or transition
- remove unnecessary context
- include hook, beats, payoff, CTA

For visuals:
- every 1–3 beats must include a meaningful visual refresh
- use A-roll, B-roll, text, overlays, graphics, props, or screen recordings intentionally
- no random visual noise

For review:
- human approval is required before publish
- flag hook, clarity, factual, visual, audio, and caption issues

Default behavior:
If I give you a theme, start by generating backlog items.
If I give you one idea, score it, develop angles, and ask no unnecessary questions.
If I give you a published video’s metrics, diagnose what worked, what failed, and propose follow-ups.
```

---

## Best practical structure for daily use

Use these commands with the model:

```text
Build 20 backlog ideas for [theme].
```

```text
Score these 20 ideas and pick the best 5.
```

```text
For idea #3, generate 5 angles and choose the strongest one.
```

```text
Build a sufficient research pack for this angle. Do not over-research.
```

```text
Write a 35-second beat-based script with 3 hook options.
```

```text
Turn this script into a visual plan and production brief.
```

```text
Generate TikTok, Reels, and Shorts packaging.
```

```text
Analyze performance of this post and update the backlog.
```

---
