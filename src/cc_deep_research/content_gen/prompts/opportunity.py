"""Prompt templates for the opportunity planning stage."""

from __future__ import annotations

from cc_deep_research.content_gen.models import StrategyMemory

GLOBAL_RULES = """\
You are planning a short-form content opportunity inside a modular workflow.

Important:
- Only do the task for this step
- Be precise and ruthless about weak themes
- If a theme is too vague, call that out explicitly
- Do not invent facts, examples, or proof
- Keep every field concrete and actionable"""

PLAN_OPPORTUNITY_SYSTEM = f"""\
{GLOBAL_RULES}

You are turning a raw content theme into a structured opportunity brief.

Task:
Analyze the theme and produce a focused editorial contract that will guide
backlog generation, research, and scoring downstream.

Requirements:
- The goal must be specific and measurable
- Audience segments must be concrete (not "everyone" or "marketers")
- Problem statements must be real, observable problems
- Platform constraints should reflect short-form video realities
- Risk constraints should flag claims that need proof
- Sub-angles should be distinct editorial directions, not restatements
- Research hypotheses should be testable claims, not wishes
- Success criteria should be measurable outcomes

Output format — use these exact headers:

Theme: (refined theme statement)
Goal: (specific content goal)
Primary audience segment: (who this is really for)
Secondary audience segments:
- (segment 1)
- (segment 2)
Problem statements:
- (problem 1)
- (problem 2)
Content objective: (what the content should accomplish)
Proof requirements:
- (requirement 1)
- (requirement 2)
Platform constraints:
- (constraint 1)
- (constraint 2)
Risk constraints:
- (risk 1)
- (risk 2)
Freshness rationale: (why this is timely now)
Sub-angles:
- (angle 1)
- (angle 2)
- (angle 3)
Research hypotheses:
- (hypothesis 1)
- (hypothesis 2)
Success criteria:
- (criterion 1)
- (criterion 2)"""


def plan_opportunity_user(
    theme: str,
    strategy: StrategyMemory,
) -> str:
    parts = [f"Theme: {theme}"]
    if strategy.niche:
        parts.append(f"Niche: {strategy.niche}")
    if strategy.content_pillars:
        parts.append(f"Content pillars: {', '.join(strategy.content_pillars)}")
    if strategy.audience_segments:
        segs = "; ".join(f"{s.name}: {s.description}" for s in strategy.audience_segments)
        parts.append(f"Known audience segments: {segs}")
    if strategy.tone_rules:
        parts.append(f"Tone rules: {', '.join(strategy.tone_rules)}")
    if strategy.forbidden_claims:
        parts.append(f"Forbidden claims: {', '.join(strategy.forbidden_claims)}")
    if strategy.proof_standards:
        parts.append(f"Proof standards: {', '.join(strategy.proof_standards)}")
    if strategy.platforms:
        parts.append(f"Target platforms: {', '.join(strategy.platforms)}")
    if strategy.past_winners:
        winners = "; ".join(w.title for w in strategy.past_winners[:5])
        parts.append(f"Past winners: {winners}")
    if strategy.past_losers:
        losers = "; ".join(loser.title for loser in strategy.past_losers[:5])
        parts.append(f"Past losers: {losers}")
    return "\n".join(parts)
