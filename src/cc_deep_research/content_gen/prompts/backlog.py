"""Prompt templates for the backlog builder and idea scorer.

Contract Version: 1.2.0

Parser expectations:
- build_backlog output: Uses `---` as block delimiter. The parser keeps a
  block only when it can extract `title` or legacy `idea`. Other parsed fields
  are optional: one_line_summary, raw_idea, constraints, category, source_theme, audience,
  persona_detail, problem, emotional_driver, urgency_level, why_now, hook,
  content_type, format_duration, key_message, call_to_action, evidence,
  proof_gap_note, expertise_reason, genericity_risk, risk_level. It also reads
  "Rejected ideas:" and "Rejection reasons:" summary fields.
- score_ideas output: Uses `---` as block delimiter, expects fields:
  idea_id, relevance, novelty, authority_fit, production_ease,
  evidence_strength, hook_strength, repurposing, total_score,
  recommendation, reason. The parser requires `idea_id`, clamps invalid
  scores into the 1-5 range, defaults invalid recommendations to `hold`,
  and optionally reads the trailing shortlist summary fields.

When editing prompts, ensure output format remains compatible with
the parser functions in agents/backlog.py (_parse_backlog_items,
_parse_scores, _derive_selection).
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import (
    BacklogItem,
    OpportunityBrief,
    StrategyMemory,
)

CONTRACT_VERSION = "1.2.0"

GLOBAL_RULES = """\
You are generating short-form video content ideas inside a modular workflow.

Important:
- Only do the task for this step
- Be precise and ruthless about weak ideas
- If an idea is vague, unprovable, or too broad, reject it
- Every idea must have a clear audience, clear payoff, and at least one evidence source
- Do not invent facts, examples, or proof
- When evidence is weak, say so"""


# ---------------------------------------------------------------------------
# Build backlog
# ---------------------------------------------------------------------------

BUILD_BACKLOG_SYSTEM = f"""\
{GLOBAL_RULES}

You are building a backlog of short-form video ideas.

Task:
Generate content ideas across three categories: trend-responsive, evergreen, and authority-building.

Requirements:
- Each idea must have a specific title and one-line summary
- Each idea must target a specific audience with a specific problem
- Each idea should narrow the persona and emotional driver when possible
- Each idea must have a clear why_now reason
- Each idea must include a hook, key message, and CTA
- Each idea must support one clear core idea for one video
- The hook must create tension, not just name the topic
- The key message must point to a specific payoff, not generic value
- Prefer ideas that naturally allow proof, example, demonstration, or comparison
- Use refined short-form formats where possible:
  Insight Breakdown, Mistake to Fix, Story-Based, Myth vs Truth,
  Tutorial / How-To, Result-First / Case Study, Opinion / Hot Take,
  Before vs After
- Reject ideas that are vague, unprovable, or too broad
- Keep only ideas with a clear audience + clear payoff + at least one evidence source

Output format — repeat this block for each idea:

---
idea_id: (leave blank)
category: trend-responsive | evergreen | authority-building
title: (specific editorial title)
one_line_summary: (one sentence summary)
raw_idea: (optional raw memo text if the idea is still rough)
constraints: (optional production, compliance, or brand constraints)
source_theme: (origin theme or source cluster)
audience: (specific audience)
persona_detail: (narrow persona detail)
problem: (specific problem)
emotional_driver: (fear, aspiration, frustration, urgency, etc.)
urgency_level: low | medium | high
why_now: (why this is timely)
hook: (opening line idea)
content_type: (format type)
format_duration: (for example 60_seconds)
key_message: (main takeaway)
call_to_action: (what to ask the viewer to do next)
evidence: (what supports this)
proof_gap_note: (what still needs proof or sourcing)
expertise_reason: (why this fits the creator's authority)
genericity_risk: low | medium | high
risk_level: low | medium | high
---

End with:
Total ideas:
Rejected ideas:
Rejection reasons:"""


def build_backlog_user(
    theme: str,
    strategy: StrategyMemory,
    *,
    count: int = 20,
    opportunity_brief: OpportunityBrief | None = None,
) -> str:
    parts = [f"Theme: {theme}", f"Target count: {count} ideas"]
    if strategy.niche:
        parts.append(f"Niche: {strategy.niche}")
    if strategy.content_pillars:
        parts.append(f"Content pillars: {', '.join(strategy.content_pillars)}")
    if strategy.audience_segments:
        segs = "; ".join(f"{s.name}: {s.description}" for s in strategy.audience_segments)
        parts.append(f"Audience segments: {segs}")
    if strategy.forbidden_claims:
        parts.append(f"Forbidden claims: {', '.join(strategy.forbidden_claims)}")
    if strategy.past_winners:
        winners = "; ".join(w.title for w in strategy.past_winners[:5])
        parts.append(f"Past winners: {winners}")

    if opportunity_brief:
        if opportunity_brief.goal:
            parts.append(f"\nGoal: {opportunity_brief.goal}")
        if opportunity_brief.primary_audience_segment:
            parts.append(f"Primary audience: {opportunity_brief.primary_audience_segment}")
        if opportunity_brief.secondary_audience_segments:
            parts.append(f"Secondary audiences: {', '.join(opportunity_brief.secondary_audience_segments)}")
        if opportunity_brief.problem_statements:
            parts.append(f"Problem statements: {'; '.join(opportunity_brief.problem_statements)}")
        if opportunity_brief.content_objective:
            parts.append(f"Content objective: {opportunity_brief.content_objective}")
        if opportunity_brief.proof_requirements:
            parts.append(f"Proof requirements: {', '.join(opportunity_brief.proof_requirements)}")
        if opportunity_brief.platform_constraints:
            parts.append(f"Platform constraints: {', '.join(opportunity_brief.platform_constraints)}")
        if opportunity_brief.risk_constraints:
            parts.append(f"Risk constraints: {', '.join(opportunity_brief.risk_constraints)}")
        if opportunity_brief.freshness_rationale:
            parts.append(f"Freshness rationale: {opportunity_brief.freshness_rationale}")
        if opportunity_brief.sub_angles:
            parts.append(f"Sub-angles to explore: {', '.join(opportunity_brief.sub_angles)}")
        if opportunity_brief.research_hypotheses:
            parts.append(f"Research hypotheses: {'; '.join(opportunity_brief.research_hypotheses)}")
        if opportunity_brief.success_criteria:
            parts.append(f"Success criteria: {'; '.join(opportunity_brief.success_criteria)}")
        if opportunity_brief.problem_statements:
            parts.append(f"Problem statements: {'; '.join(opportunity_brief.problem_statements)}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Score ideas
# ---------------------------------------------------------------------------

SCORE_IDEAS_SYSTEM = f"""\
{GLOBAL_RULES}

You are scoring short-form video ideas.

Task:
Score each idea from 1-5 on these dimensions:
- relevance: How relevant is this to the target audience?
- novelty: Is this fresh or has it been done to death?
- authority_fit: Does this match the creator's expertise?
- production_ease: Can this be produced quickly?
- evidence_strength: How strong is the supporting evidence?
- hook_strength: How compelling is the potential hook?
- repurposing: Can this be repurposed across platforms?
- opportunity_fit: How well does this idea fit the opportunity brief?
  (audience, problem, sub-angle, and proof constraints — 1-5)

Hard rules:
- Kill anything with weak evidence AND weak hook
- Penalize generic educational ideas that overlap heavily with other ideas
- Prefer ideas whose payoff is specific and whose format is obvious from the angle
- Produce_now only if total score passes the threshold
- Build a ranked shortlist from the strongest produce_now ideas only
- Pick one selected idea_id from the shortlist and explain why it won
- Be honest about weak ideas — do not inflate scores

Output format — repeat for each idea:

---
idea_id: (from input)
relevance: (1-5)
novelty: (1-5)
authority_fit: (1-5)
production_ease: (1-5)
evidence_strength: (1-5)
hook_strength: (1-5)
repurposing: (1-5)
opportunity_fit: (1-5 — how well this fits opportunity brief constraints)
expected_upside: (1-5 — expected upside potential, used for ROI gate; below 2 = fast-fail kill)
effort_tier: quick | standard | deep — estimated production effort/complexity
total_score: (sum — include opportunity_fit in the sum)
recommendation: produce_now | hold | kill
reason: (one sentence)
kill_reason: (required when recommendation is kill — why this idea fails the ROI gate)
opportunity_fit_reason: (brief explanation of how this idea satisfies the opportunity brief)
---

After all idea blocks, add:
shortlist:
- (idea_id)
- (idea_id)
selected_idea_id: (winner from shortlist, leave blank if there is no shortlist)
selection_reasoning: (why this shortlisted idea should be produced first)"""


def score_ideas_user(
    items: list[BacklogItem],
    strategy: StrategyMemory,
    *,
    threshold: int = 25,
) -> str:
    parts = [f"Scoring threshold for produce_now: {threshold}/35"]
    if strategy.niche:
        parts.append(f"Niche: {strategy.niche}")
    if strategy.proof_standards:
        parts.append(f"Proof standards: {', '.join(strategy.proof_standards)}")

    # Task 20: Include performance learnings in scoring context
    pg = strategy.performance_guidance
    if pg.winning_hooks:
        parts.append(f"\nWinning hook patterns (prior performance): {'; '.join(pg.winning_hooks[:3])}")
    if pg.failed_hooks:
        parts.append(f"Failed hook patterns to avoid: {'; '.join(pg.failed_hooks[:3])}")
    if pg.winning_framings:
        parts.append(f"Winning framing patterns: {'; '.join(pg.winning_framings[:3])}")
    if pg.failed_framings:
        parts.append(f"Failed framing patterns to avoid: {'; '.join(pg.failed_framings[:3])}")
    if pg.audience_resonance_notes:
        parts.append(f"Confirmed audience resonance: {'; '.join(pg.audience_resonance_notes[:3])}")
    if pg.proof_expectations:
        parts.append(f"Proof expectations from prior content: {'; '.join(pg.proof_expectations[:3])}")

    parts.append("")
    for item in items:
        parts.append(f"idea_id: {item.idea_id}")
        parts.append(f"category: {item.category}")
        parts.append(f"title: {item.title or item.idea}")
        parts.append(f"one_line_summary: {item.one_line_summary or item.idea}")
        parts.append(f"raw_idea: {item.raw_idea}")
        parts.append(f"constraints: {item.constraints}")
        parts.append(f"audience: {item.audience}")
        parts.append(f"persona_detail: {item.persona_detail}")
        parts.append(f"problem: {item.problem}")
        parts.append(f"emotional_driver: {item.emotional_driver}")
        parts.append(f"urgency_level: {item.urgency_level}")
        parts.append(f"hook: {item.hook or item.potential_hook}")
        parts.append(f"key_message: {item.key_message}")
        parts.append(f"call_to_action: {item.call_to_action}")
        parts.append(f"evidence: {item.evidence}")
        parts.append("---")
    return "\n".join(parts)
