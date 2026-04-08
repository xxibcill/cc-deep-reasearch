"""Prompt templates for the backlog builder and idea scorer.

Contract Version: 1.0.0

Parser expectations:
- build_backlog output: Uses `---` as block delimiter. The parser keeps a
  block only when it can extract `idea`. Other parsed fields are optional:
  category, audience, problem, source, why_now, potential_hook,
  content_type, evidence, risk_level. It also reads "Rejected ideas:" and
  "Rejection reasons:" summary fields.
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

CONTRACT_VERSION = "1.0.0"

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
- Each idea must target a specific audience with a specific problem
- Each idea must have a clear why_now reason
- Each idea must include a potential hook
- Reject ideas that are vague, unprovable, or too broad
- Keep only ideas with a clear audience + clear payoff + at least one evidence source

Output format — repeat this block for each idea:

---
idea_id: (leave blank)
category: trend-responsive | evergreen | authority-building
idea: (one sentence)
audience: (specific audience)
problem: (specific problem)
source: (where this idea came from)
why_now: (why this is timely)
potential_hook: (opening line idea)
content_type: (format type)
evidence: (what supports this)
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

Hard rules:
- Kill anything with weak evidence AND weak hook
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
total_score: (sum)
recommendation: produce_now | hold | kill
reason: (one sentence)
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
    parts.append("")
    for item in items:
        parts.append(f"idea_id: {item.idea_id}")
        parts.append(f"category: {item.category}")
        parts.append(f"idea: {item.idea}")
        parts.append(f"audience: {item.audience}")
        parts.append(f"problem: {item.problem}")
        parts.append(f"potential_hook: {item.potential_hook}")
        parts.append(f"evidence: {item.evidence}")
        parts.append("---")
    return "\n".join(parts)
