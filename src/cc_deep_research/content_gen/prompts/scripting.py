"""Prompt templates for the 10-step scripting pipeline.

Contract Version: 1.2.1

Parser expectations for each step:
- Step 1 (define_core_inputs): Expects "Topic:", "Outcome:", "Audience:" fields
- Step 2 (define_angle): Expects "Angle:", "Content Type:", "Core Tension:" and
  optionally "Why this angle works:"
- Step 3 (choose_structure): Expects "Chosen Structure:", "Beat List:" and
  optionally "Why this structure fits:"
- Step 4 (define_beat_intents): Expects either legacy "beat_name: intent" lines
  or repeated grounded beat blocks with beat/proof/claim references
- Step 5 (generate_hooks): Expects numbered hooks with required "Best Hook:" and
  optional "Why it is strongest:"
- Step 6 (draft_script): Expects any non-empty script body; later steps do not
  parse labeled sub-sections from the draft
- Step 7 (add_retention_mechanics): Prefers a "Revised Script:" section ending
  before "Then add:" or "Retention changes made:", but falls back to the full response
- Step 8 (tighten): Prefers a "Tightened Script:" section ending before
  "Then add:" or "Cuts / improvements made:", but falls back to the full response
- Step 9 (add_visual_notes): Stores the full response as the annotated script and
  optionally extracts inline visual notes from "[Beat] ... [Visual]" patterns
- Step 10 (run_qc): Expects parseable QC checklist lines and optionally
  "Weakest parts:" and "Final Script:" sections; if "Final Script:" is absent,
  the source script is preserved

When editing prompts, ensure output format remains compatible with
the parser in agents/scripting.py (_parse_step1_output, etc.).
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import (
    AngleDefinition,
    ArgumentMap,
    BeatIntentMap,
    CoreInputs,
    ScriptStructure,
    ScriptVersion,
    StrategyMemory,
)

CONTRACT_VERSION = "1.2.0"

REFINED_CONTENT_TYPES = """\
- Insight Breakdown
- Mistake to Fix
- Story-Based
- Myth vs Truth
- Tutorial / How-To
- Result-First / Case Study
- Opinion / Hot Take
- Before vs After"""

REFINED_STRUCTURE_LIBRARY = """\
A. Insight Breakdown
Hook
Why this matters
Point 1
Point 2
Point 3
Core takeaway
CTA

B. Mistake to Fix
Hook
Pain point
What most people do wrong
What to do instead
Why it works
Expected result
CTA

C. Story-Based
Hook
Starting situation
Conflict / struggle
Turning point
Lesson
Payoff / result
CTA

D. Myth vs Truth
Hook
The popular belief
Why people believe it
Why it breaks down
What's actually true
What to do with that truth
CTA

E. Tutorial / How-To
Hook
Desired outcome
Step 1
Step 2
Step 3
Common pitfall
CTA

F. Result-First / Case Study
Hook with result
Context
What changed
Why it worked
Lesson
CTA

G. Opinion / Hot Take
Hook
Bold claim
Why most people disagree
Your reasoning
Implication
CTA

H. Before vs After
Hook
Before
What changed
After
Lesson
CTA"""

UNIVERSAL_SHORT_FORM_RULES = """\
Universal short-form performance rules:
- The hook must create tension, not just announce the topic
- The second beat must justify attention fast with pain, surprise, proof, or urgency
- One video = one core idea; supporting points must reinforce the same thesis
- The payoff must be specific and observable, not generic
- Prefer proof, example, or contrast when the claim needs support
- The CTA should match the format and feel like the natural next move"""


def _render_research_context(research_context: str) -> str:
    if not research_context.strip():
        return ""
    return f"\nResearch Context:\n{research_context.strip()}"


def _render_original_brief(raw_idea: str) -> str:
    if not raw_idea.strip():
        return ""
    return (
        "\nOriginal Brief (preserve any still-relevant constraints, preferences, "
        f"must-includes, and must-avoids):\n{raw_idea.strip()}"
    )


def _render_argument_map(argument_map: ArgumentMap | None) -> str:
    if argument_map is None:
        return ""

    parts = [
        "Argument Map:",
        f"Thesis: {argument_map.thesis}",
        f"Audience belief to challenge: {argument_map.audience_belief_to_challenge}",
        f"Core mechanism: {argument_map.core_mechanism}",
    ]

    if argument_map.safe_claims:
        parts.append("Safe claims:")
        parts.extend(
            f"- {claim.claim_id}: {claim.claim} (proofs: {', '.join(claim.supporting_proof_ids) or 'none'})"
            for claim in argument_map.safe_claims
        )
    if argument_map.proof_anchors:
        parts.append("Proof anchors:")
        parts.extend(
            f"- {proof.proof_id}: {proof.summary} (use: {proof.usage_note or 'none'})"
            for proof in argument_map.proof_anchors
        )
    if argument_map.counterarguments:
        parts.append("Counterarguments:")
        parts.extend(
            f"- {counter.counterargument_id}: {counter.counterargument} -> {counter.response}"
            for counter in argument_map.counterarguments
        )
    if argument_map.unsafe_claims:
        parts.append("Unsafe claims to avoid as facts:")
        parts.extend(f"- {claim.claim_id}: {claim.claim}" for claim in argument_map.unsafe_claims)
    if argument_map.beat_claim_plan:
        parts.append("Beat claim plan:")
        parts.extend(
            (
                f"- {beat.beat_name} ({beat.beat_id}): {beat.goal} "
                f"| claims: {', '.join(beat.claim_ids) or 'none'} "
                f"| proofs: {', '.join(beat.proof_anchor_ids) or 'none'} "
                f"| counters: {', '.join(beat.counterargument_ids) or 'none'} "
                f"| next: {beat.transition_note or 'none'}"
            )
            for beat in argument_map.beat_claim_plan
        )
    return "\n".join(parts)


def _append_context_handoff(
    parts: list[str],
    *,
    raw_idea: str = "",
    inputs: CoreInputs | None = None,
    angle: AngleDefinition | None = None,
    structure: ScriptStructure | None = None,
    beat_intents: BeatIntentMap | None = None,
    argument_map: ArgumentMap | None = None,
    best_hook: str = "",
    tone: str = "",
    cta: str = "",
    research_context: str = "",
) -> None:
    brief = _render_original_brief(raw_idea)
    if brief:
        parts.append(brief)
    if inputs:
        parts.append(
            f"\nOriginal intent:\n"
            f"Topic: {inputs.topic}\n"
            f"Outcome: {inputs.outcome}\n"
            f"Audience: {inputs.audience}"
        )
    if angle:
        parts.append(
            f"\nAngle:\n{angle.angle}\n"
            f"Content Type: {angle.content_type}\n"
            f"Core Tension: {angle.core_tension}"
        )
    if structure:
        beat_list = "\n".join(f"- {beat}" for beat in structure.beat_list)
        parts.append(
            f"\nChosen Structure:\n{structure.chosen_structure}\n"
            f"Beat List:\n{beat_list}"
        )
    if beat_intents:
        beat_lines = "\n".join(
            _format_beat_intent_line(beat)
            for beat in beat_intents.beats
        )
        parts.append(f"\nBeat Intents:\n{beat_lines}")
    argument_map_text = _render_argument_map(argument_map)
    if argument_map_text:
        parts.append(f"\n{argument_map_text}")
    if best_hook:
        parts.append(f"\nSelected Hook:\n{best_hook}")
    if tone:
        parts.append(f"\nTone:\n{tone}")
    if cta:
        parts.append(f"\nCTA goal:\n{cta}")
    research = _render_research_context(research_context)
    if research:
        parts.append(research)

GLOBAL_RULES = """\
You are generating short-form video scripting outputs inside a modular workflow.

Important:
- Only do the task for this step
- Do not jump ahead
- Do not include extra explanation unless requested
- Be precise and ruthless about weak ideas
- If the input is vague, fix the vagueness
- If the angle is weak, strengthen it
- If the writing is generic, sharpen it
- If an Original Brief is provided, preserve its constraints unless they conflict with this step's explicit task
- If an Argument Map is provided, treat it as the grounding source of truth for what can be claimed
- Once a structure is chosen, treat its beat order and beat count as locked unless a step explicitly tells you to re-choose the structure
- Once a best hook is chosen, treat that exact line as locked unless a step explicitly tells you to regenerate hooks
- Optimize for spoken delivery, retention, and compression"""


def _format_beat_intent_line(beat) -> str:
    details: list[str] = []
    if getattr(beat, "beat_id", ""):
        details.append(f"beat_id={beat.beat_id}")
    if getattr(beat, "claim_ids", None):
        details.append(f"claim_ids={', '.join(beat.claim_ids)}")
    if getattr(beat, "proof_anchor_ids", None):
        details.append(f"proof_ids={', '.join(beat.proof_anchor_ids)}")
    if getattr(beat, "counterargument_ids", None):
        details.append(f"counter_ids={', '.join(beat.counterargument_ids)}")
    if getattr(beat, "transition_note", ""):
        details.append(f"transition={beat.transition_note}")
    suffix = f" [{' | '.join(details)}]" if details else ""
    return f"- {beat.beat_name}: {beat.intent}{suffix}"


# ---------------------------------------------------------------------------
# Step 1: Define Core Inputs
# ---------------------------------------------------------------------------

STEP1_SYSTEM = f"""\
{GLOBAL_RULES}

You are helping define a short-form video idea.

Task:
Take the raw idea and convert it into 3 clear inputs:
1. Topic
2. Outcome
3. Audience

Requirements:
- Keep each field concise
- Make the topic specific
- Make the outcome concrete and useful
- Define the audience narrowly enough to guide tone and examples
- If the idea is vague, refine it instead of preserving vagueness

Output format:

Topic:
Outcome:
Audience:"""


def step1_user(raw_idea: str) -> str:
    return f"Raw idea:\n{raw_idea}"


# ---------------------------------------------------------------------------
# Step 2: Define the Angle
# ---------------------------------------------------------------------------

STEP2_SYSTEM = f"""\
{GLOBAL_RULES}

You are defining the strategic angle for a short-form video.

Task:
Using the Topic, Outcome, and Audience, define the strongest angle.

Requirements:
- Make the angle specific, not broad
- The angle must make the topic worth watching
- Avoid generic educational framing
- Find tension, contradiction, surprise, or a sharp benefit
- Pick the content type that best fits the viewer payoff, not the safest label
- Avoid overlapping educational framings when a more specific format fits better
- If the topic is weak, improve the angle instead of forcing a bland one

Choose one content type:
{REFINED_CONTENT_TYPES}

Output format:

Angle:
Content Type:
Core Tension:
Why this angle works:"""


def step2_user(
    inputs: CoreInputs,
    raw_idea: str = "",
    strategy: StrategyMemory | None = None,
) -> str:
    parts = [
        f"Topic:\n{inputs.topic}",
        f"Outcome:\n{inputs.outcome}",
        f"Audience:\n{inputs.audience}",
    ]
    brief = _render_original_brief(raw_idea)
    if brief:
        parts.append(brief)

    # P3-T1: Strategy guidance for angle definition
    if strategy:
        if strategy.tone_rules:
            parts.append(f"Tone rules: {', '.join(strategy.tone_rules)}")
        if strategy.cta_strategy:
            if strategy.cta_strategy.allowed_cta_types:
                parts.append(f"Allowed CTA types: {', '.join(strategy.cta_strategy.allowed_cta_types)}")
            if strategy.cta_strategy.default_by_content_goal:
                defaults = [f"{k}: {v}" for k, v in strategy.cta_strategy.default_by_content_goal.items()]
                parts.append(f"CTA defaults by goal: {'; '.join(defaults[:3])}")
        if strategy.forbidden_topics:
            parts.append(f"Forbidden topics: {', '.join(strategy.forbidden_topics)}")
        if strategy.banned_tropes:
            parts.append(f"Banned tropes: {', '.join(strategy.banned_tropes)}")
        # Performance learnings for framing
        pg = strategy.performance_guidance
        if pg.winning_framings:
            parts.append(f"Winning framing patterns: {'; '.join(pg.winning_framings[:3])}")
        if pg.failed_framings:
            parts.append(f"Failed framing patterns to avoid: {'; '.join(pg.failed_framings[:3])}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Step 3: Choose the Best Structure
# ---------------------------------------------------------------------------

STEP3_SYSTEM = f"""\
{GLOBAL_RULES}

You are selecting the best structure for a short-form video.

Task:
Choose the strongest script structure based on the angle and content type.

Available structures:
{REFINED_STRUCTURE_LIBRARY}

{UNIVERSAL_SHORT_FORM_RULES}

Requirements:
- Choose the structure that best fits the idea
- Do not choose based on symmetry or habit
- Briefly justify the choice
- Select one structure template and keep the exact same beat sequence as that template
- Do not add beats, remove beats, merge beats, split beats, or rename beats
- If none of the templates fit cleanly, choose the closest valid template instead of inventing a hybrid
- Make sure the first two beats earn attention quickly
- Prefer structures that surface proof, example, or contrast before the payoff feels delayed
- If the content type is educational, avoid redundant "just explain more" beat naming
- Keep the beat list aligned to one core thesis

Output format:

Chosen Structure:
Why this structure fits:
Beat List:

1.
2.
3. ..."""


def step3_user(inputs: CoreInputs, angle: AngleDefinition, raw_idea: str = "") -> str:
    parts = [
        f"Topic:\n{inputs.topic}",
        f"Outcome:\n{inputs.outcome}",
        f"Audience:\n{inputs.audience}",
        f"Angle:\n{angle.angle}",
        f"Content Type:\n{angle.content_type}",
        f"Core Tension:\n{angle.core_tension}",
    ]
    brief = _render_original_brief(raw_idea)
    if brief:
        parts.append(brief)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 4: Define Beat Intent
# ---------------------------------------------------------------------------

STEP4_SYSTEM = f"""\
{GLOBAL_RULES}

You are planning a short-form video before writing the script.

Task:
Define the purpose of each beat in the chosen structure.

Requirements:
- Do not write the script yet
- Each beat should state what it must accomplish
- Each beat must move the viewer forward
- Avoid vague intent like "explain more" or "add detail"
- If a beat has no strong purpose, revise or remove it
- If an Argument Map is provided, use it as the primary grounding source
- Map beats only to safe claims and proof anchors that support what the script can honestly say
- Never attach an unsafe claim to a beat as if it were settled fact
- Research context is fallback only when it helps sharpen a beat without changing the supported claim set

Output format:

---
Beat Name: Hook
Intent: (what this beat must do)
Claim IDs: claim_1
Proof Anchor IDs: proof_1
Counterargument IDs:
Transition Note: (how this beat moves to the next beat)
---
(repeat for each beat)"""


def step4_user(
    inputs: CoreInputs,
    angle: AngleDefinition,
    structure: ScriptStructure,
    raw_idea: str = "",
    research_context: str = "",
    argument_map: ArgumentMap | None = None,
) -> str:
    beats = "\n".join(f"- {b}" for b in structure.beat_list)
    parts = [
        f"Topic:\n{inputs.topic}",
        f"Outcome:\n{inputs.outcome}",
        f"Audience:\n{inputs.audience}",
        f"Angle:\n{angle.angle}",
        f"Content Type:\n{angle.content_type}",
        f"Core Tension:\n{angle.core_tension}",
        f"Chosen Structure:\n{structure.chosen_structure}",
        f"Beat List:\n{beats}",
    ]
    brief = _render_original_brief(raw_idea)
    if brief:
        parts.append(brief)
    argument = _render_argument_map(argument_map)
    if argument:
        parts.append(argument)
    research = _render_research_context(research_context)
    if research:
        parts.append(research)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 5: Generate Hooks
# ---------------------------------------------------------------------------

STEP5_SYSTEM = f"""\
{GLOBAL_RULES}

You are generating hooks for a short-form video.

Task:
Write 10 hook options based on the angle and core tension.

Requirements:
- Each hook must create curiosity, tension, surprise, or direct relevance
- Avoid generic hook language
- Avoid clickbait that the script cannot justify
- Keep hooks speakable and concise
- Prefer specificity over abstraction
- Vary the hook style across the set
- Hooks must be materially different from one another, not minor rewrites of the same line
- Avoid topic-only hooks that do not imply a payoff or consequence
- At least 3 hooks should make the payoff concrete through a result, contrast, or example
- The strongest hook should set up a fast second beat, not a slow explanation
- If an Argument Map is provided, only imply or state safe claims that the script can support
- Do not turn unsafe claims into bold factual hooks

Use a mix of:
- Contrarian
- Direct pain
- Curiosity gap
- Warning
- Sharp claim
- Credibility hook (reference a specific fact or proof point from research)

Additional rule:
- If research context includes proof points or key facts, at least 2 hooks should reference them directly

Output format:

1.
2.
3.
4.
5.
6.
7.
8.
9.
10.

Then add:

Best Hook:
Why it is strongest:"""


def step5_user(
    inputs: CoreInputs,
    angle: AngleDefinition,
    beat_intents: BeatIntentMap,
    raw_idea: str = "",
    research_context: str = "",
    argument_map: ArgumentMap | None = None,
    strategy: StrategyMemory | None = None,
) -> str:
    beat_lines = "\n".join(_format_beat_intent_line(beat) for beat in beat_intents.beats)
    parts = [
        f"Topic:\n{inputs.topic}",
        f"Outcome:\n{inputs.outcome}",
        f"Audience:\n{inputs.audience}",
        f"Angle:\n{angle.angle}",
        f"Core Tension:\n{angle.core_tension}",
        f"Beat Intent Map:\n{beat_lines}",
    ]
    brief = _render_original_brief(raw_idea)
    if brief:
        parts.append(brief)
    argument = _render_argument_map(argument_map)
    if argument:
        parts.append(argument)
    research = _render_research_context(research_context)
    if research:
        parts.append(research)

    # P3-T1: Strategy hook guidance
    if strategy:
        pg = strategy.performance_guidance
        if pg.winning_hooks:
            parts.append(f"\nWinning hook patterns: {'; '.join(pg.winning_hooks[:3])}")
        if pg.failed_hooks:
            parts.append(f"Failed hook patterns to avoid: {'; '.join(pg.failed_hooks[:3])}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 5b: Generate CTA
# ---------------------------------------------------------------------------

STEP5B_SYSTEM = f"""\
{GLOBAL_RULES}

You are generating call-to-action (CTA) options for a short-form video.

Task:
Write 5 CTA options based on the topic, outcome, and angle.

Requirements:
- Each CTA must be concise and action-oriented
- CTAs should motivate immediate action from the audience
- Vary the style: some direct, some benefit-focused, some urgency-driven
- CTAs must be materially different from one another
- Keep CTAs speakable and natural-sounding
- Do not use generic phrases like "subscribe for more"

Output format:

1.
2.
3.
4.
5.

Then add:

Best CTA:
Why it is strongest:"""


def step5b_user(
    inputs: CoreInputs,
    angle: AngleDefinition,
    raw_idea: str = "",
    research_context: str = "",
) -> str:
    parts = [
        f"Topic:\n{inputs.topic}",
        f"Outcome:\n{inputs.outcome}",
        f"Audience:\n{inputs.audience}",
        f"Angle:\n{angle.angle}",
    ]
    brief = _render_original_brief(raw_idea)
    if brief:
        parts.append(brief)
    research = _render_research_context(research_context)
    if research:
        parts.append(research)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 6: Draft Full Script
# ---------------------------------------------------------------------------

STEP6_SYSTEM = f"""\
{GLOBAL_RULES}

You are writing a short-form video script.

Task:
Write a full script using the selected hook and beat plan.

Requirements:
- Follow the chosen structure
- Keep the exact same beat order, beat count, and beat labels from the chosen structure
- Use the beat intents exactly
- Do not add, remove, merge, split, or rename beats
- Use the Argument Map and beat-level claim/proof links as the source of truth for what the script can state
- Only state claims that are supported by the mapped proof anchors for each beat
- Do not mention citations, IDs, or source labels in the spoken script
- Do not convert unsafe claims into confident statements
- Use exactly one hook line and exactly one CTA line in the full script
- The hook line must use the selected hook, not a rewritten alternate
- Do not include multiple opening hooks, backup hooks, CTA variants, or repeated CTA lines
- Make the first two beats do the heaviest retention work
- The second beat must quickly add tension, pain, proof, or surprise
- Keep the script centered on one core idea
- Make the payoff specific and observable for the stated audience
- Use proof, example, or contrast when the structure calls for it
- One idea per sentence
- 8-12 words per sentence when possible
- Keep it conversational and speakable
- No filler
- No repeated ideas
- No essay-style transitions
- Every line must add new information, tension, or payoff
- Keep the script compact enough for short-form delivery

Target:
- Around 20-40 seconds
- Hard cap: 120 words unless absolutely necessary

Output format:

Hook:
...

[Next Beat]: ...
[Next Beat]: ...

Payoff:
...

CTA:
..."""


def step6_user(
    inputs: CoreInputs,
    angle: AngleDefinition,
    structure: ScriptStructure,
    beat_intents: BeatIntentMap,
    best_hook: str,
    raw_idea: str = "",
    research_context: str = "",
    argument_map: ArgumentMap | None = None,
    *,
    tone: str = "",
    cta: str = "",
    strategy: StrategyMemory | None = None,
) -> str:
    beat_lines = "\n".join(_format_beat_intent_line(beat) for beat in beat_intents.beats)
    parts = [
        f"Topic:\n{inputs.topic}",
        f"Outcome:\n{inputs.outcome}",
        f"Audience:\n{inputs.audience}",
        f"Angle:\n{angle.angle}",
        f"Core Tension:\n{angle.core_tension}",
        f"Chosen Structure:\n{structure.chosen_structure}",
        f"Beat Intent Map:\n{beat_lines}",
        f"Best Hook:\n{best_hook}",
    ]
    brief = _render_original_brief(raw_idea)
    if brief:
        parts.append(brief)
    argument = _render_argument_map(argument_map)
    if argument:
        parts.append(argument)
    if tone:
        parts.append(f"Tone:\n{tone}")
    if cta:
        parts.append(f"CTA goal:\n{cta}")
    research = _render_research_context(research_context)
    if research:
        parts.append(research)

    # P3-T1: Strategy guidance for scripting
    if strategy:
        if strategy.proof_standards:
            parts.append(f"Proof standards: {', '.join(strategy.proof_standards)}")
        if strategy.claim_to_proof_rules:
            for cpr in strategy.claim_to_proof_rules[:3]:
                parts.append(f"Claim-to-proof [{cpr.claim_type}]: {', '.join(cpr.required_proof)}")
        if strategy.cta_strategy:
            if strategy.cta_strategy.allowed_cta_types:
                parts.append(f"Allowed CTA types: {', '.join(strategy.cta_strategy.allowed_cta_types)}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 7: Add Retention Mechanics
# ---------------------------------------------------------------------------

STEP7_SYSTEM = f"""\
{GLOBAL_RULES}

You are improving retention in a short-form video script.

Task:
Revise the draft to improve pacing and viewer hold.

Apply these retention rules:
- Every 1-2 lines should add a new idea, shift perspective, or increase tension
- Tighten the first two beats before touching anything else
- Add at least 2 of the following where useful:
  - Contrast
  - Open loop
  - Emphasis phrase
  - Pattern interrupt
  - Sharp transition
- Do not add fluff
- Do not make the script longer unless the added line clearly improves retention
- Preserve clarity and natural spoken rhythm
- If the payoff lands late, move proof or example earlier
- Preserve the supported-claim boundaries from the Argument Map
- Preserve exactly one hook line and at most one CTA line
- Do not turn the opening into multiple hook lines
- Do not add a second CTA
- Preserve the exact beat order, beat count, and beat labels from the chosen structure
- Do not add, remove, merge, split, or rename beats while revising

Output format:

Revised Script:
...

Then add:

Retention changes made:

- ...
- ...
- ..."""


def step7_user(
    draft: ScriptVersion,
    *,
    raw_idea: str = "",
    core_inputs: CoreInputs | None = None,
    angle: AngleDefinition | None = None,
    structure: ScriptStructure | None = None,
    beat_intents: BeatIntentMap | None = None,
    argument_map: ArgumentMap | None = None,
    best_hook: str = "",
    tone: str = "",
    cta: str = "",
    research_context: str = "",
) -> str:
    parts = [f"Draft Script:\n{draft.content}"]
    _append_context_handoff(
        parts,
        raw_idea=raw_idea,
        inputs=core_inputs,
        angle=angle,
        structure=structure,
        beat_intents=beat_intents,
        argument_map=argument_map,
        best_hook=best_hook,
        tone=tone,
        cta=cta,
        research_context=research_context,
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 8: Tightening Pass
# ---------------------------------------------------------------------------

STEP8_SYSTEM = f"""\
{GLOBAL_RULES}

You are tightening a short-form video script.

Task:
Make the script sharper, shorter, and more speakable.

Editing rules:
- Remove filler words
- Remove repeated meaning
- Replace generic wording with specific wording
- Shorten long sentences
- Cut any line that does not add value
- Preserve the core angle and flow
- Keep natural spoken rhythm
- Keep the first two beats sharp and fast
- If the payoff is vague, rewrite it into a specific viewer result
- Keep the script inside the supported claims established by the Argument Map
- Do not over-polish into robotic language
- Preserve exactly one hook line and at most one CTA line
- If the script contains duplicate hooks or duplicate CTAs, collapse them into the single strongest version
- Preserve the exact beat order, beat count, and beat labels from the chosen structure
- Do not add, remove, merge, split, or rename beats during tightening

Output format:

Tightened Script:
...

Then add:

Cuts / improvements made:

- ...
- ...
- ..."""


def step8_user(
    revised: ScriptVersion,
    *,
    raw_idea: str = "",
    core_inputs: CoreInputs | None = None,
    angle: AngleDefinition | None = None,
    structure: ScriptStructure | None = None,
    beat_intents: BeatIntentMap | None = None,
    argument_map: ArgumentMap | None = None,
    best_hook: str = "",
    core_tension: str = "",
    tone: str = "",
    cta: str = "",
    research_context: str = "",
) -> str:
    parts = [f"Revised Script:\n{revised.content}"]
    if core_tension:
        parts.append(f"\nCore Tension (must be preserved):\n{core_tension}")
    _append_context_handoff(
        parts,
        raw_idea=raw_idea,
        inputs=core_inputs,
        angle=angle,
        structure=structure,
        beat_intents=beat_intents,
        argument_map=argument_map,
        best_hook=best_hook,
        tone=tone,
        cta=cta,
        research_context=research_context,
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 9: Add Visual Notes
# ---------------------------------------------------------------------------

STEP9_SYSTEM = f"""\
{GLOBAL_RULES}

You are adding optional visual notes to a short-form video script.

Task:
Add simple visual annotations only where they improve clarity, emphasis, or pacing.

Allowed annotations:
[Cut]
[Zoom]
[Text on screen]
[B-roll]

Rules:
- Use sparingly
- Do not annotate every line
- Only add notes where visuals strengthen delivery
- Keep notes simple and production-friendly
- Do not add visual annotations that imply unsupported claims
- Keep exactly one [Hook] line and at most one [CTA] line in the annotated output
- Do not split the hook or CTA into multiple labeled lines
- Preserve the exact beat order, beat count, and beat labels from the chosen structure

Output format:

[Beat Name]: "Line..."

[Visual note if needed]

[Beat Name]: "Line...\""""


def step9_user(
    tightened: ScriptVersion,
    *,
    raw_idea: str = "",
    core_inputs: CoreInputs | None = None,
    angle: AngleDefinition | None = None,
    structure: ScriptStructure | None = None,
    beat_intents: BeatIntentMap | None = None,
    argument_map: ArgumentMap | None = None,
    best_hook: str = "",
    tone: str = "",
    cta: str = "",
    research_context: str = "",
) -> str:
    parts = [f"Tightened Script:\n{tightened.content}"]
    _append_context_handoff(
        parts,
        raw_idea=raw_idea,
        inputs=core_inputs,
        angle=angle,
        structure=structure,
        beat_intents=beat_intents,
        argument_map=argument_map,
        best_hook=best_hook,
        tone=tone,
        cta=cta,
        research_context=research_context,
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 10: Final QC
# ---------------------------------------------------------------------------

STEP10_SYSTEM = f"""\
{GLOBAL_RULES}

You are performing final quality control on a short-form video script.

Task:
Evaluate the script against the checklist below.

Checklist:
- Understandable in one pass
- Hook creates curiosity, tension, or relevance
- Second beat escalates quickly instead of stalling in setup
- Exactly one hook is present
- At most one CTA is present
- Beat order matches the chosen structure exactly
- Beat count matches the chosen structure exactly
- No beats were renamed, merged, split, added, or removed
- No vague or generic phrasing
- Every line adds value
- Spoken rhythm feels natural
- Structure is coherent
- No unnecessary length
- One clear core idea runs through the script
- Payoff is specific and clear
- CTA does not feel disconnected
- Script delivers on the stated outcome for the target audience
- Core tension from the angle is preserved throughout
- Each beat fulfills its stated intent
- Only supported claims are stated as fact

Instructions:
- First, give a strict pass/fail for each checklist item
- Then identify the 3 weakest parts
- Then produce the final improved script
- Be direct; do not protect weak writing
- If the script has duplicate hook lines or duplicate CTA lines, fix that in the final script

Output format:

QC Review:

- Item: Pass/Fail
- Item: Pass/Fail

Weakest parts:

1.
2.
3.

Final Script:
..."""


def step10_user(
    script: ScriptVersion,
    *,
    label: str = "Script",
    raw_idea: str = "",
    core_inputs: CoreInputs | None = None,
    angle: AngleDefinition | None = None,
    structure: ScriptStructure | None = None,
    beat_intents: BeatIntentMap | None = None,
    argument_map: ArgumentMap | None = None,
    best_hook: str = "",
    tone: str = "",
    cta: str = "",
    research_context: str = "",
    strategy: StrategyMemory | None = None,
) -> str:
    parts = [f"{label}:\n{script.content}"]
    _append_context_handoff(
        parts,
        raw_idea=raw_idea,
        inputs=core_inputs,
        angle=angle,
        structure=structure,
        beat_intents=beat_intents,
        argument_map=argument_map,
        best_hook=best_hook,
        tone=tone,
        cta=cta,
        research_context=research_context,
    )

    # P3-T1: Strategy guidance for QC
    if strategy:
        if strategy.proof_standards:
            parts.append(f"Proof standards: {', '.join(strategy.proof_standards)}")
        if strategy.forbidden_claims:
            parts.append(f"Forbidden claims: {', '.join(strategy.forbidden_claims)}")
        if strategy.banned_tropes:
            parts.append(f"Banned tropes: {', '.join(strategy.banned_tropes)}")

    return "\n".join(parts)
