# Select Beat Structure Prompt

This file contains a self-contained prompt for selecting the best beat structure when the AI only receives:

- `Content Pillar`
- `Angle Statement`

It assumes the AI has no prior context, no research pack, no audience brief, and no access to other docs.

## Expected Input

Use this prompt with exactly these two inputs:

```text
Content Pillar: <pillar name>
Angle Statement: <one-sentence script angle>
```

Examples of content pillars:

- Pricing
- Positioning
- Retention
- Growth
- Conversion
- Product education
- Founder story
- Operations
- AI workflow

## Copy/Paste Prompt

```md
You are selecting the best beat structure for a short-form script.

You have only two inputs:

1. Content Pillar
2. Angle Statement

You do not have any other context.
Do not ask follow-up questions.
Do not assume you will receive research, target audience notes, product specs, or platform instructions later.
Work only from the Content Pillar and Angle Statement below.

Your job:
Choose exactly one beat structure that best fits the script's likely narrative job.

Core decision rule:

- The angle statement matters more than the content pillar.
- The content pillar provides domain context.
- The angle statement provides the real narrative shape.
- If pillar and angle point in different directions, optimize for the angle.

Important constraints:

- Choose one structure only.
- Do not invent a hybrid structure.
- Do not rename beats.
- Do not add beats, remove beats, merge beats, or split beats.
- Do not add a default `Bridge` beat just to clarify the hook.
- Choose the structure that will create the clearest tension, fastest retention, and strongest payoff.
- Favor structures that make the second beat justify attention quickly.
- If the angle is ambiguous, choose the closest valid structure and explain why.

Universal short-form rules:

- The hook must create tension, not just announce the topic.
- The hook should usually be one short spoken line, ideally under about 3 seconds.
- The second beat must justify attention fast with pain, surprise, proof, contrast, or urgency.
- The second beat should usually clarify the hook or deliver the first payoff.
- One script should center on one core idea.
- The payoff must be specific and observable.
- The CTA should feel like the natural next move.

How to think:

1. Read the Content Pillar as the domain or category the script belongs to.
2. Read the Angle Statement as the real editorial promise.
3. Infer the likely narrative job:
   - explain
   - correct a mistake
   - tell a story
   - overturn a belief
   - teach a process
   - prove a result
   - argue a strong opinion
   - show transformation
4. Choose the structure whose beats best serve that narrative job.

Structure library:

A. Insight Breakdown
Best for:

- analytical education
- mechanism explanation
- multi-part reasoning
- expert breakdowns that need a clear sequence

Use when:

- the angle promises understanding
- the script needs to unpack why something works
- the audience needs a layered explanation, not just a correction or story

Strengths:

- clear and modular
- good for nuanced ideas
- useful when the angle has 2-3 reinforcing points

Risks:

- can feel generic or list-like
- can get slow if proof or surprise arrives too late
- should not be used when the angle is really a mistake correction, story, or contrarian reversal

Beat sequence:
Hook
Why this matters
Point 1
Point 2
Point 3
Core takeaway
CTA

What each beat is for:

- Hook: open with tension, surprise, or a sharp claim
- Why this matters: make the viewer care immediately and clarify why the hook matters
- Point 1: first supporting idea or mechanism
- Point 2: deepen the case or add contrast
- Point 3: complete the reasoning with the strongest final support
- Core takeaway: compress the lesson into one sharp conclusion
- CTA: give the next move

B. Mistake to Fix
Best for:

- practical advice
- correction content
- "stop doing this, do this instead" angles
- workflow or execution improvements

Use when:

- the angle exposes a common error
- the script is built around a bad default and a better replacement
- the audience wants a fix more than a theory

Strengths:

- immediate tension
- naturally useful
- easy to make specific and actionable

Risks:

- weak if the "mistake" is obvious
- generic if the fix is vague
- should not be used when the real value comes from proof, story, or belief reversal

Beat sequence:
Hook
Pain point
What most people do wrong
What to do instead
Why it works
Expected result
CTA

What each beat is for:

- Hook: frame the cost, danger, or missed upside
- Pain point: make the audience feel the problem clearly and confirm the hook fast
- What most people do wrong: name the faulty default
- What to do instead: give the better move
- Why it works: explain the mechanism or logic
- Expected result: show the likely payoff
- CTA: tell the viewer what to try next

C. Story-Based
Best for:

- founder lessons
- personal experience
- case-style journeys with emotional movement
- transformation through a turning point

Use when:

- the angle works because of sequence and change over time
- the lesson is stronger when delivered through an event or struggle
- the narrative needs a before, conflict, and shift

Strengths:

- emotionally engaging
- memorable
- good for credibility through lived experience

Risks:

- setup can take too long
- weak if there is no real turning point
- should not be used when the angle is primarily instructional or analytical

Beat sequence:
Hook
Starting situation
Conflict / struggle
Turning point
Lesson
Payoff / result
CTA

What each beat is for:

- Hook: create curiosity about what changed
- Starting situation: establish the initial condition quickly without turning into slow setup
- Conflict / struggle: show tension, friction, or failure
- Turning point: identify the decision or realization that changed everything
- Lesson: extract the principle
- Payoff / result: show the concrete outcome
- CTA: point to the next action or reflection

D. Myth vs Truth
Best for:

- contrarian takes
- belief reversal
- positioning and category education
- angles that challenge what the audience currently believes

Use when:

- the angle says the common belief is wrong, incomplete, or misleading
- the script's power comes from reframing
- the viewer needs a mental model shift before advice will land

Strengths:

- very strong tension
- fast attention capture
- excellent for category myths and strategic reframes

Risks:

- weak if the myth is not actually common
- weak if the "truth" is not more useful than the myth
- should not be used if the angle is just a tutorial or case study

Beat sequence:
Hook
The popular belief
Why people believe it
Why it breaks down
What's actually true
What to do with that truth
CTA

What each beat is for:

- Hook: challenge the default belief fast
- The popular belief: state the belief clearly and make the hook legible immediately
- Why people believe it: show why it sounds plausible
- Why it breaks down: expose the flaw, blind spot, or limit
- What's actually true: replace the myth with a better model
- What to do with that truth: turn the model into action
- CTA: give the natural next step

E. Tutorial / How-To
Best for:

- procedural education
- implementation guidance
- framework execution
- angles that promise a repeatable path

Use when:

- the angle promises a process or method
- the viewer wants steps, not just insight
- the value is in sequence and application

Strengths:

- concrete
- easy to follow
- good for operational or product-education content

Risks:

- can become generic if the steps are obvious
- can feel flat if there is no meaningful pitfall or payoff
- should not be used when the angle is mainly opinion, story, or myth-busting

Beat sequence:
Hook
Desired outcome
Step 1
Step 2
Step 3
Common pitfall
CTA

What each beat is for:

- Hook: make the result feel worth learning
- Desired outcome: define the end state clearly and cash out the hook fast
- Step 1: start the process
- Step 2: continue with the most important middle action
- Step 3: complete the core path
- Common pitfall: prevent failure or misuse
- CTA: tell the viewer what to do next

F. Result-First / Case Study
Best for:

- proof-driven angles
- performance wins
- mini case studies
- "here's what happened and why" scripts

Use when:

- the angle leads with an outcome
- the result itself is the hook
- the script needs proof before theory

Strengths:

- immediate credibility
- strong when the result is concrete
- naturally supports proof and lessons

Risks:

- weak if the result is vague or unimpressive
- can feel braggy if the lesson is thin
- should not be used when the angle is mostly a belief reversal or tutorial

Beat sequence:
Hook with result
Context
What changed
Why it worked
Lesson
CTA

What each beat is for:

- Hook with result: lead with the outcome in one short opening line
- Context: establish the starting point fast and clarify why the result matters
- What changed: name the intervention or shift
- Why it worked: explain the mechanism
- Lesson: generalize the principle
- CTA: direct the next move

G. Opinion / Hot Take
Best for:

- polarized viewpoints
- category arguments
- strong judgment calls
- deliberate disagreement with common advice

Use when:

- the angle is a forceful stance
- the script should feel like a sharp argument
- the value comes from conviction and reasoning

Strengths:

- high energy
- strong tension
- good for bold positioning

Risks:

- weak if the claim is not defensible
- can become empty provocation without reasoning
- should not be used when the angle really needs steps, case proof, or story sequencing

Beat sequence:
Hook
Bold claim
Why most people disagree
Your reasoning
Implication
CTA

What each beat is for:

- Hook: open with the sharp edge of the take
- Bold claim: make the position explicit and confirm the hook quickly
- Why most people disagree: show the mainstream view
- Your reasoning: defend the position clearly
- Implication: explain what changes if your take is right
- CTA: point to the next move

H. Before vs After
Best for:

- transformation
- comparisons
- process-driven change
- angles built around contrast between old state and new state

Use when:

- the angle centers on what changed between two states
- the viewer needs contrast more than abstract explanation
- the script benefits from showing improvement clearly

Strengths:

- simple and visual
- naturally contrast-driven
- good for demonstrating change in behavior, workflow, or results

Risks:

- weak if the "before" and "after" are not meaningfully different
- can feel shallow if the change mechanism is missing
- should not be used when the angle is mostly myth-busting, pure opinion, or step-by-step instruction

Beat sequence:
Hook
Before
What changed
After
Lesson
CTA

What each beat is for:

- Hook: make the contrast feel important
- Before: show the original state fast so the contrast lands immediately
- What changed: identify the key change
- After: show the improved state
- Lesson: explain the principle behind the shift
- CTA: give the next move

Selection heuristics:

- Choose Myth vs Truth when the angle overturns a common belief.
- Choose Mistake to Fix when the angle is really about correcting a bad default.
- Choose Tutorial / How-To when the angle promises a process, method, or sequence.
- Choose Result-First / Case Study when the outcome itself is the strongest hook.
- Choose Story-Based when the lesson depends on narrative change over time.
- Choose Opinion / Hot Take when the main value is a bold, defensible stance.
- Choose Before vs After when the central asset is contrast between two states.
- Choose Insight Breakdown when the angle needs explanation across multiple reinforcing points.

Content pillar guidance:

- Strategy, positioning, category, market, or brand pillars often fit Myth vs Truth, Opinion / Hot Take, or Insight Breakdown.
- Retention, conversion, growth, product, or operations pillars often fit Mistake to Fix, Tutorial / How-To, Result-First / Case Study, or Before vs After.
- Founder, career, team, or personal-learning pillars often fit Story-Based, Result-First / Case Study, or Before vs After.
- Educational or technical pillars often fit Insight Breakdown or Tutorial / How-To.

Output format:

Content Pillar:
Angle Statement:
Likely Narrative Job:
Chosen Structure:
Why this structure fits:
Why the second beat will hold attention:
Rejected alternatives:

- <structure>: <why it is not the best fit>
- <structure>: <why it is not the best fit>

Beat List:

1. <beat>
2. <beat>
3. <beat>
4. <beat>
5. <beat>
6. <beat>
7. <beat if applicable>

Beat-by-beat purpose:

- <beat>: <what this beat must accomplish in this specific script>
- <beat>: <what this beat must accomplish in this specific script>
- <beat>: <what this beat must accomplish in this specific script>
- <beat>: <what this beat must accomplish in this specific script>
- <beat>: <what this beat must accomplish in this specific script>
- <beat>: <what this beat must accomplish in this specific script>
- <beat if applicable>: <what this beat must accomplish in this specific script>

Inputs:
Content Pillar: [PASTE CONTENT PILLAR]
Angle Statement: [PASTE ANGLE STATEMENT]
```

## Notes

This prompt is intentionally self-contained. It repeats:

- the available structures
- the beat sequence for each structure
- when to use each structure
- failure modes for each structure
- selection heuristics based on pillar and angle

That makes it safe to use in isolation with a fresh model context.
