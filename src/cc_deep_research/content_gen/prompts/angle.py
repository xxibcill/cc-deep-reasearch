"""Prompt templates for the angle generator.

Contract Version: 1.0.0

Parser expectations:
- generate output: Uses `---` as block delimiter, expects fields:
  angle_id, target_audience, viewer_problem, core_promise, primary_takeaway,
  lens, format, tone, cta, why_this_version_should_exist
  A block is kept only when it includes target_audience, viewer_problem,
  core_promise, and primary_takeaway. The parser also reads the trailing
  summary fields "Best angle_id:" and "Selection reasoning:".

When editing prompts, ensure output format remains compatible with
the parser in agents/angle.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import BacklogItem, StrategyMemory

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are generating editorial angles for short-form video inside a modular workflow.

Important:
- Only do the task for this step
- Do not jump ahead
- Topic and angle are not the same thing
- An angle is a specific editorial framing that makes a topic worth watching
- Be precise and ruthless about weak angles
- If an angle is generic, strengthen it"""


ANGLE_SYSTEM = f"""\
{GLOBAL_RULES}

You are generating 3-5 editorial angles for a selected content idea.

Task:
Turn one idea into multiple distinct editorial angles. Each angle must be
a complete editorial decision — not just a restatement of the topic.

Selection criteria for the strongest angle:
- Narrowest audience fit
- Clearest promise
- Highest contrast from competitor content
- Easiest visual expression

Output format — repeat for each angle:

---
angle_id: (leave blank)
target_audience: (specific audience for this angle)
viewer_problem: (what problem does the viewer have)
core_promise: (what will they get from watching)
primary_takeaway: (the one thing they should remember)
lens: (editorial lens: contrarian, how-to, myth-bust, story, etc.)
format: (delivery format: talking head, screen recording, demonstration, etc.)
tone: (tone: direct, conversational, urgent, playful, etc.)
cta: (call to action)
why_this_version_should_exist: (why this angle is different from what exists)
---

End with:
Best angle_id:
Selection reasoning:"""


def angle_user(item: BacklogItem, strategy: StrategyMemory) -> str:
    parts = [
        f"Idea: {item.idea}",
        f"Audience: {item.audience}",
        f"Problem: {item.problem}",
        f"Category: {item.category}",
        f"Potential hook: {item.potential_hook}",
        f"Evidence: {item.evidence}",
    ]
    if strategy.niche:
        parts.append(f"Niche: {strategy.niche}")
    if strategy.tone_rules:
        parts.append(f"Tone rules: {', '.join(strategy.tone_rules)}")
    if strategy.offer_cta_rules:
        parts.append(f"CTA rules: {', '.join(strategy.offer_cta_rules)}")
    return "\n".join(parts)
