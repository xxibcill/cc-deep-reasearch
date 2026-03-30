# AI Video Scripting Prompt System

## Operating Rules

Use these rules across the full workflow:

```md
You are writing short-form video scripts.

Rules:

- Optimize for clarity, retention, and spoken delivery
- Do not write in essay format
- Do not explain beyond what is needed
- Prefer specificity over generality
- Every line must add new information, tension, or payoff
- Avoid filler, repetition, and soft wording
- Keep language natural and speakable
- Short-form priority: concise, sharp, high signal
- If the idea is weak or unclear, say so directly and refine it before continuing
```

---

# STEP 1 — Define Core Inputs

## Prompt

```md
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
Audience:
```

## Input to provide

```md
Raw idea:
[PASTE IDEA]
```

## Output handed to next step

```md
Topic:
Outcome:
Audience:
```

---

# STEP 2 — Define the Angle

This is the most important filter. Do not skip it.

## Prompt

```md
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
Why this angle works:
```

## Input to provide

```md
Topic:
[FROM STEP 1]

Outcome:
[FROM STEP 1]

Audience:
[FROM STEP 1]
```

## Output handed to next step

```md
Topic:
Outcome:
Audience:
Angle:
Content Type:
Core Tension:
```

---

# STEP 3 — Choose the Best Structure

Do not force every idea into 3 points.

## Prompt

```md
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

B. Mistake → Fix
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
What’s True
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
3. ...
```

## Input to provide

```md
Topic:
Outcome:
Audience:
Angle:
Content Type:
Core Tension:
```

## Output handed to next step

```md
Topic:
Outcome:
Audience:
Angle:
Content Type:
Core Tension:
Chosen Structure:
Beat List:
```

---

# STEP 4 — Define Intent for Each Beat

This step prevents weak writing later.

## Prompt

```md
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
...
```

## Input to provide

```md
Topic:
Outcome:
Audience:
Angle:
Content Type:
Core Tension:
Chosen Structure:
Beat List:
```

## Output handed to next step

```md
Topic:
Outcome:
Audience:
Angle:
Core Tension:
Chosen Structure:
Beat Intent Map:

- Beat:
  Intent:
- Beat:
  Intent:
```

---

# STEP 5 — Generate Hooks First

Do not write the full script before pressure-testing the hook.

## Prompt

```md
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
3. ...
4.

Then add:

Best Hook:
Why it is strongest:
```

## Input to provide

```md
Topic:
Outcome:
Audience:
Angle:
Core Tension:
Beat Intent Map:
```

## Output handed to next step

```md
Topic:
Outcome:
Audience:
Angle:
Core Tension:
Chosen Structure:
Beat Intent Map:
Best Hook:
```

---

# STEP 6 — Draft the Full Script

Now write the first full version.

## Prompt

```md
You are writing a short-form video script.

Task:
Write a full script using the selected hook and beat plan.

Requirements:

- Follow the chosen structure
- Use the beat intents exactly
- Use exactly one hook line and exactly one CTA line in the script
- The hook line must use the selected hook, not a new alternate
- Do not include backup hooks, CTA options, or repeated CTA lines
- One idea per sentence
- 8–12 words per sentence when possible
- Keep it conversational and speakable
- No filler
- No repeated ideas
- No essay-style transitions
- Every line must add new information, tension, or payoff
- Keep the script compact enough for short-form delivery

Target:

- Around 20–40 seconds
- Hard cap: 120 words unless absolutely necessary

Output format:

Hook:
...

[Next Beat]: ...
[Next Beat]: ...

Payoff:
...

CTA:
...
```

## Input to provide

```md
Topic:
Outcome:
Audience:
Angle:
Core Tension:
Chosen Structure:
Beat Intent Map:
Best Hook:
```

## Output handed to next step

```md
Draft Script:
[PASTE OUTPUT]
```

---

# STEP 7 — Add Retention Mechanics

This is not a rewrite from scratch. It is a targeted enhancement pass.

## Prompt

```md
You are improving retention in a short-form video script.

Task:
Revise the draft to improve pacing and viewer hold.

Apply these retention rules:

- Every 1–2 lines should add a new idea, shift perspective, or increase tension
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
- ...
```

## Input to provide

```md
Draft Script:
[FROM STEP 6]
```

## Output handed to next step

```md
Revised Script:
[PASTE OUTPUT]
```

---

# STEP 8 — Tightening Pass

This is where most mediocre scripts get fixed.

## Prompt

```md
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
- ...
```

## Input to provide

```md
Revised Script:
[FROM STEP 7]
```

## Output handed to next step

```md
Tightened Script:
[PASTE OUTPUT]
```

---

# STEP 9 — Add Optional Visual Notes

Only do this if visuals genuinely improve clarity, pacing, or emphasis.

## Prompt

```md
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

[Beat Name]: "Line..."
```

## Input to provide

```md
Tightened Script:
[FROM STEP 8]
```

## Output handed to next step

```md
Annotated Script:
[PASTE OUTPUT]
```

---

# STEP 10 — Final Quality Control

This step decides whether the script is actually ready.

## Prompt

```md
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
...
```

## Input to provide

```md
Annotated Script:
[FROM STEP 9]
```

If you skipped visuals, use the tightened script instead.

## Final output

```md
QC Review:
...

Final Script:
...
```

---

# Recommended Handoff Format Between Steps

Because you said each step gets fresh context, use this rule:

## Pass forward only:

- finalized outputs
- compact structured fields
- no old drafts unless the next step needs them

## Do not pass forward:

- chain-of-thought
- rejected alternatives
- long explanations
- earlier exploratory outputs unless they are selected

---

# Minimal Pipeline Version

If you want speed over maximum control, use this shorter flow:

```md
1. Define Topic / Outcome / Audience
2. Define Angle / Content Type / Core Tension
3. Choose Structure
4. Define Beat Intent
5. Generate 10 Hooks and select best one
6. Draft Full Script
7. Add Retention Mechanics
8. Tighten
9. QC and finalize
```

---

# Best-Practice Master Prompt for the Whole System

Use this at the top of every step if needed:

```md
You are generating short-form video scripting outputs inside a modular workflow.

Important:

- Only do the task for this step
- Do not jump ahead
- Do not include extra explanation unless requested
- Be precise and ruthless about weak ideas
- If the input is vague, fix the vagueness
- If the angle is weak, strengthen it
- If the writing is generic, sharpen it
- Optimize for spoken delivery, retention, and compression
```

---

# Important Improvement for Your System

Your original workflow was missing a proper **decision gate**. Add this rule:

```md
If a step produces weak or vague output, do not continue.
Revise that step until the output is specific and strong enough to guide the next one.
```

That matters because bad scripting usually starts from:

- weak angle
- weak hook
- weak beat intent

Not from the final wording.

---

# Copy-Paste Ready Version

Here is the compressed system you can directly use as your SOP:

```md
SYSTEM GOAL:
Generate short-form video scripts through a modular workflow with minimal context handoff.

GLOBAL RULES:

- Optimize for clarity, retention, and spoken delivery
- No essay writing
- No filler
- No repeated ideas
- Every line must add value
- Fix vague inputs before continuing
- Do not proceed with weak outputs

STEP 1:
Define Topic / Outcome / Audience

STEP 2:
Define Angle / Content Type / Core Tension

STEP 3:
Choose best structure:

- Insight Breakdown
- Mistake → Fix
- Story-Based
- Myth vs Truth

STEP 4:
Define intent for each beat

STEP 5:
Generate 10 hooks and select the strongest one

STEP 6:
Write full script

- conversational
- one idea per sentence
- 8–12 words when possible
- 20–40 seconds
- max 120 words

STEP 7:
Add retention mechanics

- contrast
- open loops
- emphasis
- pattern interrupts

STEP 8:
Tighten

- cut filler
- cut repetition
- sharpen wording

STEP 9:
Add optional visual notes only if useful

STEP 10:
Run strict QC

- pass/fail checklist
- identify weak parts
- produce final script
```
