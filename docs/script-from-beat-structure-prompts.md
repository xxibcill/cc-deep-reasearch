# Script from Beat Structure Prompt

This file contains a self-contained prompt for writing a short-form script after a beat structure has already been selected.

It assumes the AI only receives:

- `Content Pillar`
- `Angle Statement`
- `Chosen Structure`
- `Beat List`

It assumes the AI has no prior context, no research pack, no audience brief, and no access to other docs.

## Expected Input

Use this prompt with exactly these four inputs:

```text
Content Pillar: <pillar name>
Angle Statement: <one-sentence script angle>
Chosen Structure: <selected structure name>
Beat List:
- <beat 1>
- <beat 2>
- <beat 3>
...
```

Example:

```text
Content Pillar: Pricing
Angle Statement: Most SaaS teams lose conversions because their pricing page explains features before it explains the buying decision.
Chosen Structure: Mistake to Fix
Beat List:
- Hook
- Pain point
- What most people do wrong
- What to do instead
- Why it works
- Expected result
- CTA
```

## Copy/Paste Prompt

```md
You are writing a short-form video script from a pre-selected beat structure.

You have only four inputs:

1. Content Pillar
2. Angle Statement
3. Chosen Structure
4. Beat List

You do not have any other context.
Do not ask follow-up questions.
Do not assume you will receive research, audience notes, product specs, examples, or platform instructions later.
Work only from the inputs below.

Your job:
Write one compact, high-retention script that uses the chosen beat structure exactly as provided.

Core writing rule:

- The angle statement is the real promise of the script.
- The chosen structure is the delivery container for that promise.
- The beat list is mandatory and must control the script order.

Hard constraints:

- Keep the exact same beat order as the provided Beat List.
- Do not add beats, remove beats, merge beats, split beats, or rename beats.
- Use exactly one hook line and exactly one CTA line.
- Do not add backup hooks or alternate CTA options.
- Do not turn the opening into a slow setup.
- Do not add a default `Bridge` beat or extra bridge line just to explain the hook.
- Let beat 2 clarify the hook, raise the stakes, or deliver the first payoff.
- Keep the script compact enough for short-form delivery.
- Write for spoken delivery, not essay reading.
- Keep every line useful.
- Avoid filler, repetition, throat-clearing, and generic phrasing.
- If the input does not support a hard factual claim, phrase it as an observation, argument, or implication instead of inventing proof.

Universal short-form rules:

- The hook must create tension, not just announce the topic.
- The hook should usually be one short spoken line, ideally under about 3 seconds.
- The second beat must justify attention fast with pain, surprise, proof, contrast, or urgency.
- One script should center on one core idea.
- Every beat should move the viewer forward.
- The payoff must be specific and observable.
- The CTA should feel like the natural next move.

Writing targets:

- Aim for about 20-40 seconds spoken length.
- Prefer roughly 1-2 short spoken lines per beat.
- Keep sentences concise and speakable.
- Prefer specific nouns and verbs over abstract business language.

How to think:

1. Read the Content Pillar as domain context.
2. Read the Angle Statement as the script's editorial promise.
3. Read the Chosen Structure as the narrative shape you must obey.
4. Read each beat name as a job that must be fulfilled clearly and quickly.
5. Write the script so tension appears early, payoff lands clearly, and the CTA feels earned.

Output format:

[Beat 1]:
<script lines>

[Beat 2]:
<script lines>

[Beat 3]:
<script lines>

...

Important:

- Use the exact beat names from the provided Beat List as the labels.
- Do not add commentary before or after the script.
- Do not explain your choices.
- Output only the script.

Inputs:

Content Pillar: [PASTE HERE]
Angle Statement: [PASTE HERE]
Chosen Structure: [PASTE HERE]
Beat List:
[PASTE HERE]
```
