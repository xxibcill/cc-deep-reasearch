"""Prompt templates for the 10-step scripting pipeline.

Contract Version: 1.0.0

Parser expectations for each step:
- Step 1 (define_core_inputs): Expects "Topic:", "Outcome:", "Audience:" fields
- Step 2 (define_angle): Expects "Angle:", "Content Type:", "Core Tension:" and
  optionally "Why this angle works:"
- Step 3 (choose_structure): Expects "Chosen Structure:", "Beat List:" and
  optionally "Why this structure fits:"
- Step 4 (define_beat_intents): Expects numbered list with "beat_name: intent" format
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
    BeatIntentMap,
    CoreInputs,
    ScriptStructure,
    ScriptVersion,
)

CONTRACT_VERSION = "1.0.0"


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


def _append_context_handoff(
    parts: list[str],
    *,
    raw_idea: str = "",
    inputs: CoreInputs | None = None,
    angle: AngleDefinition | None = None,
    structure: ScriptStructure | None = None,
    beat_intents: BeatIntentMap | None = None,
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
        parts.append(f"\nChosen Structure:\n{structure.chosen_structure}\nBeat List:\n{beat_list}")
    if beat_intents:
        beat_lines = "\n".join(f"- {b.beat_name}: {b.intent}" for b in beat_intents.beats)
        parts.append(f"\nBeat Intents:\n{beat_lines}")
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
- Optimize for spoken delivery, retention, and compression"""


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
- If the topic is weak, improve the angle instead of forcing a bland one

Choose one content type:
- Contrarian
- Mistake
- Framework
- Insight
- Story
- Myth vs Truth

Output format:

Angle:
Content Type:
Core Tension:
Why this angle works:"""


def step2_user(inputs: CoreInputs, raw_idea: str = "") -> str:
    parts = [
        f"Topic:\n{inputs.topic}",
        f"Outcome:\n{inputs.outcome}",
        f"Audience:\n{inputs.audience}",
    ]
    brief = _render_original_brief(raw_idea)
    if brief:
        parts.append(brief)
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

A. Insight Breakdown
Hook
Context / Setup
Main Point 1
Main Point 2
Main Point 3
Payoff / Insight
CTA

B. Mistake to Fix
Hook
Problem
Common Mistake
Better Approach
Expected Result
CTA

C. Story-Based
Hook
Setup
Turning Point
Lesson
Payoff
CTA

D. Myth vs Truth
Hook
Common Belief
Why It Fails
What's True
Implication
CTA

Requirements:
- Choose the structure that best fits the idea
- Do not choose based on symmetry or habit
- Briefly justify the choice
- If needed, lightly adapt the structure names to fit the topic, but keep the logic intact

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
- If research context is provided, use it to inform beat purposes — cite specific facts, proof points, or examples where they strengthen a beat's intent

Output format:

[Beat Name]: [clear intent]
[Beat Name]: [clear intent]
[Beat Name]: [clear intent]
..."""


def step4_user(
    inputs: CoreInputs,
    angle: AngleDefinition,
    structure: ScriptStructure,
    raw_idea: str = "",
    research_context: str = "",
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
) -> str:
    beat_lines = "\n".join(f"- {b.beat_name}: {b.intent}" for b in beat_intents.beats)
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
- Use the beat intents exactly
- Use exactly one hook line and exactly one CTA line in the full script
- The hook line must use the selected hook, not a rewritten alternate
- Do not include multiple opening hooks, backup hooks, CTA variants, or repeated CTA lines
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
    *,
    tone: str = "",
    cta: str = "",
) -> str:
    beat_lines = "\n".join(f"- {b.beat_name}: {b.intent}" for b in beat_intents.beats)
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
    if tone:
        parts.append(f"Tone:\n{tone}")
    if cta:
        parts.append(f"CTA goal:\n{cta}")
    research = _render_research_context(research_context)
    if research:
        parts.append(research)
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
- Add at least 2 of the following where useful:
  - Contrast
  - Open loop
  - Emphasis phrase
  - Pattern interrupt
  - Sharp transition
- Do not add fluff
- Do not make the script longer unless the added line clearly improves retention
- Preserve clarity and natural spoken rhythm
- Preserve exactly one hook line and at most one CTA line
- Do not turn the opening into multiple hook lines
- Do not add a second CTA

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
- Do not over-polish into robotic language
- Preserve exactly one hook line and at most one CTA line
- If the script contains duplicate hooks or duplicate CTAs, collapse them into the single strongest version

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
- Keep exactly one [Hook] line and at most one [CTA] line in the annotated output
- Do not split the hook or CTA into multiple labeled lines

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
- Exactly one hook is present
- At most one CTA is present
- No vague or generic phrasing
- Every line adds value
- Spoken rhythm feels natural
- Structure is coherent
- No unnecessary length
- Payoff is clear
- CTA does not feel disconnected
- Script delivers on the stated outcome for the target audience
- Core tension from the angle is preserved throughout
- Each beat fulfills its stated intent

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
    best_hook: str = "",
    tone: str = "",
    cta: str = "",
    research_context: str = "",
) -> str:
    parts = [f"{label}:\n{script.content}"]
    _append_context_handoff(
        parts,
        raw_idea=raw_idea,
        inputs=core_inputs,
        angle=angle,
        structure=structure,
        beat_intents=beat_intents,
        best_hook=best_hook,
        tone=tone,
        cta=cta,
        research_context=research_context,
    )
    return "\n".join(parts)
