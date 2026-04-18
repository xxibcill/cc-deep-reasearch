"""Prompt templates for the angle generator.

Contract Version: 1.1.0

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

CONTRACT_VERSION = "1.1.0"

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
- Best fit between the idea and a proven short-form format

Refined short-form format library:
- Insight Breakdown
- Mistake to Fix
- Story-Based
- Myth vs Truth
- Tutorial / How-To
- Result-First / Case Study
- Opinion / Hot Take
- Before vs After

Reaction / Response and List / Roundup are allowed only when the idea genuinely
needs them; do not default to them when one of the refined formats is stronger.

Task 19 — Competitive Differentiation:
For each angle, explicitly address:
- differentiation_summary: Why this angle is distinct from the baseline market
  framing for this topic (what commonly repeated advice does it reframe or reject?)
- market_framing_challenged: What common/repeated market framing this angle
  reframes or contradicts
- genericity_risks: Known failure modes for this angle (e.g., could slide into
  clichéd framing, interchangeable takeaways, generic advice without backing)

Output format — repeat for each angle:

---
angle_id: (leave blank)
target_audience: (specific audience for this angle)
viewer_problem: (what problem does the viewer have)
core_promise: (what will they get from watching)
primary_takeaway: (the one specific thing they should remember)
lens: (editorial lens: use one refined short-form format name or a close variant)
format: (delivery format: talking head, screen recording, demonstration, etc.)
tone: (tone: direct, conversational, urgent, playful, etc.)
cta: (call to action)
why_this_version_should_exist: (why this angle is different from what exists)
differentiation_summary: (why this angle is distinct from baseline market framing)
market_framing_challenged: (common/repeated framing this angle reframes or contradicts)
genericity_risks:
- (specific failure mode: clichéd framing, generic takeaway, etc.)
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

    # Core strategy fields
    if strategy.niche:
        parts.append(f"Niche: {strategy.niche}")
    if strategy.tone_rules:
        parts.append(f"Tone rules: {', '.join(strategy.tone_rules)}")
    if strategy.offer_cta_rules:
        parts.append(f"CTA rules: {', '.join(strategy.offer_cta_rules)}")

    # P3-T1: Performance learnings - hook and framing guidance
    pg = strategy.performance_guidance
    if pg.winning_hooks:
        parts.append(f"\nConfirmed winning hook patterns: {'; '.join(pg.winning_hooks[:3])}")
    if pg.failed_hooks:
        parts.append(f"Failed hook patterns to avoid: {'; '.join(pg.failed_hooks[:3])}")
    if pg.winning_framings:
        parts.append(f"Confirmed winning framings: {'; '.join(pg.winning_framings[:3])}")
    if pg.failed_framings:
        parts.append(f"Failed framing patterns to avoid: {'; '.join(pg.failed_framings[:3])}")
    if pg.audience_resonance_notes:
        parts.append(f"Audience resonance signals: {'; '.join(pg.audience_resonance_notes[:3])}")

    # P3-T1: CTA strategy from strategy
    if strategy.cta_strategy:
        if strategy.cta_strategy.allowed_cta_types:
            parts.append(f"Allowed CTA types: {', '.join(strategy.cta_strategy.allowed_cta_types)}")
        if strategy.cta_strategy.default_by_content_goal:
            defaults = [f"{k}: {v}" for k, v in strategy.cta_strategy.default_by_content_goal.items()]
            parts.append(f"CTA defaults by goal: {'; '.join(defaults[:3])}")

    # P3-T1: Platform rules
    if strategy.platform_rules:
        for pr in strategy.platform_rules[:3]:
            if pr.guidance:
                parts.append(f"Platform rule [{pr.platform}]: {pr.guidance}")

    # P3-T1: Forbidden content
    if strategy.forbidden_claims:
        parts.append(f"Forbidden claims: {', '.join(strategy.forbidden_claims)}")
    if strategy.forbidden_topics:
        parts.append(f"Forbidden topics: {', '.join(strategy.forbidden_topics)}")
    if strategy.banned_tropes:
        parts.append(f"Banned tropes: {', '.join(strategy.banned_tropes)}")

    # P3-T1: Proof requirements
    if strategy.proof_rules:
        parts.append(f"Proof rules: {'; '.join(strategy.proof_rules)}")
    if strategy.proof_standards:
        parts.append(f"Proof standards: {', '.join(strategy.proof_standards)}")

    # P3-T1: Claim-to-proof mapping
    if strategy.claim_to_proof_rules:
        for cpr in strategy.claim_to_proof_rules[:3]:
            parts.append(f"Claim-to-proof [{cpr.claim_type}]: {', '.join(cpr.required_proof)}")

    # P3-T1: Audience universe
    if strategy.allowed_audience_universe:
        parts.append(f"Allowed audience universe: {', '.join(strategy.allowed_audience_universe[:3])}")

    # P3-T1: Content pillars
    if strategy.content_pillars:
        pillar_names = [p.name for p in strategy.content_pillars]
        parts.append(f"Content pillars: {', '.join(pillar_names)}")

    return "\n".join(parts)
