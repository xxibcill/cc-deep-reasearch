"""Prompt templates for the 10-step scripting pipeline."""

from __future__ import annotations

from cc_deep_research.content_gen.models import (
    AngleDefinition,
    BeatIntentMap,
    CoreInputs,
    ScriptStructure,
    ScriptVersion,
)


def _render_research_context(research_context: str) -> str:
    if not research_context.strip():
        return ""
    return f"\nResearch Context:\n{research_context.strip()}"

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


def step2_user(inputs: CoreInputs) -> str:
    return f"Topic:\n{inputs.topic}\n\nOutcome:\n{inputs.outcome}\n\nAudience:\n{inputs.audience}"


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


def step3_user(inputs: CoreInputs, angle: AngleDefinition) -> str:
    return (
        f"Topic:\n{inputs.topic}\n"
        f"Outcome:\n{inputs.outcome}\n"
        f"Audience:\n{inputs.audience}\n"
        f"Angle:\n{angle.angle}\n"
        f"Content Type:\n{angle.content_type}\n"
        f"Core Tension:\n{angle.core_tension}"
    )


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

Output format:

[Beat Name]: [clear intent]
[Beat Name]: [clear intent]
[Beat Name]: [clear intent]
..."""


def step4_user(
    inputs: CoreInputs,
    angle: AngleDefinition,
    structure: ScriptStructure,
    research_context: str = "",
) -> str:
    beats = "\n".join(f"- {b}" for b in structure.beat_list)
    return (
        f"Topic:\n{inputs.topic}\n"
        f"Outcome:\n{inputs.outcome}\n"
        f"Audience:\n{inputs.audience}\n"
        f"Angle:\n{angle.angle}\n"
        f"Content Type:\n{angle.content_type}\n"
        f"Core Tension:\n{angle.core_tension}\n"
        f"Chosen Structure:\n{structure.chosen_structure}\n"
        f"Beat List:\n{beats}"
        f"{_render_research_context(research_context)}"
    )


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
    research_context: str = "",
) -> str:
    beat_lines = "\n".join(f"- {b.beat_name}: {b.intent}" for b in beat_intents.beats)
    return (
        f"Topic:\n{inputs.topic}\n"
        f"Outcome:\n{inputs.outcome}\n"
        f"Audience:\n{inputs.audience}\n"
        f"Angle:\n{angle.angle}\n"
        f"Core Tension:\n{angle.core_tension}\n"
        f"Beat Intent Map:\n{beat_lines}"
        f"{_render_research_context(research_context)}"
    )


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
    research_context: str = "",
) -> str:
    beat_lines = "\n".join(f"- {b.beat_name}: {b.intent}" for b in beat_intents.beats)
    return (
        f"Topic:\n{inputs.topic}\n"
        f"Outcome:\n{inputs.outcome}\n"
        f"Audience:\n{inputs.audience}\n"
        f"Angle:\n{angle.angle}\n"
        f"Core Tension:\n{angle.core_tension}\n"
        f"Chosen Structure:\n{structure.chosen_structure}\n"
        f"Beat Intent Map:\n{beat_lines}\n"
        f"Best Hook:\n{best_hook}"
        f"{_render_research_context(research_context)}"
    )


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

Output format:

Revised Script:
...

Then add:

Retention changes made:

- ...
- ...
- ..."""


def step7_user(draft: ScriptVersion) -> str:
    return f"Draft Script:\n{draft.content}"


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

Output format:

Tightened Script:
...

Then add:

Cuts / improvements made:

- ...
- ...
- ..."""


def step8_user(revised: ScriptVersion) -> str:
    return f"Revised Script:\n{revised.content}"


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

Output format:

[Beat Name]: "Line..."

[Visual note if needed]

[Beat Name]: "Line...\""""


def step9_user(tightened: ScriptVersion) -> str:
    return f"Tightened Script:\n{tightened.content}"


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
- No vague or generic phrasing
- Every line adds value
- Spoken rhythm feels natural
- Structure is coherent
- No unnecessary length
- Payoff is clear
- CTA does not feel disconnected

Instructions:
- First, give a strict pass/fail for each checklist item
- Then identify the 3 weakest parts
- Then produce the final improved script
- Be direct; do not protect weak writing

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


def step10_user(script: ScriptVersion, *, label: str = "Script") -> str:
    return f"{label}:\n{script.content}"
