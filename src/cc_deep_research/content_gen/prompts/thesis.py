"""Prompt templates for the unified thesis generator (P3-T2).

Contract Version: 2.0.0

This module replaces the previous two-stage angle + argument_map flow with a
single unified thesis artifact. The artifact combines:
- Selected angle fields (editorial framing, target audience, promise, tone)
- Thesis structure (thesis statement, belief to challenge, mechanism)
- Support structure (proof anchors, claims, counterarguments, beat plan)

Parser expectations:
- The response mixes scalar fields with repeated '---' blocks
- Angle/selection fields: angle_id, target_audience, viewer_problem, core_promise,
  primary_takeaway, lens, format, tone, cta, why_this_version_should_exist,
  differentiation_summary, genericity_risks (list), market_framing_challenged,
  selection_reasoning
- Thesis fields: thesis, audience_belief_to_challenge, core_mechanism
- proof_anchors: repeated --- blocks with proof_id, summary, source_ids, usage_note
- counterarguments: repeated --- blocks with counterargument_id, counterargument, response, response_proof_ids
- safe_claims: repeated --- blocks with claim_id, claim, supporting_proof_ids, note
- unsafe_claims: repeated --- blocks with claim_id, claim, supporting_proof_ids, note
- beat_claim_plan: repeated --- blocks with beat_id, beat_name, goal, claim_ids,
  proof_anchor_ids, counterargument_ids, transition_note
- Differentiation: what_this_contributes, genericity_flags (list), differentiation_stategy

When editing prompts, ensure output format remains compatible with
the parser in agents/thesis.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import BacklogItem, ResearchPack, StrategyMemory

CONTRACT_VERSION = "2.0.0"

GLOBAL_RULES = """\
You are generating a unified thesis artifact that combines editorial angle
selection with argument design for short-form video content.

Important:
- Produce ONE complete thesis artifact in a single pass
- Do not generate angle options first and then separately design the argument
- The angle and thesis are one artifact — select the angle framing AND build
  the supporting argument structure together
- Only use evidence from the provided research pack
- Do not invent proof, statistics, or case studies
- Separate safe claims from unsafe claims"""


THESIS_SYSTEM = f"""\
{GLOBAL_RULES}

Task:
Turn one content idea into a unified thesis artifact that specifies:
1. The selected editorial angle (who it's for, what problem it solves, why it's different)
2. The core thesis statement and what belief it challenges
3. The supporting argument structure (proof, claims, counterarguments)
4. The narrative beat plan that scripts will follow

Research Analysis First:
Before constructing the thesis, review the provided research pack for:
- Key facts and proof points that support the argument
- Audience insights that inform targeting
- Gaps or uncertainties that affect claim safety
- Unsafe or disputed claims to avoid

Angle Selection Criteria:
- Narrowest audience fit
- Clearest promise
- Highest contrast from competitor content
- Easiest visual expression
- Best fit between the idea and a proven short-form format

Format Library (use as lens/labels):
- Insight Breakdown
- Mistake to Fix
- Story-Based
- Myth vs Truth
- Tutorial / How-To
- Result-First / Case Study
- Opinion / Hot Take
- Before vs After

Differentiation Check:
For the selected angle, explicitly address:
- differentiation_summary: Why this angle is distinct from baseline market framing
- market_framing_challenged: What common/repeated framing this angle reframes
- genericity_risks: Failure modes (clichéd framing, generic advice, interchangeable takeaways)

Thesis Construction:
- thesis: One clear expert point, not a topic label
- audience_belief_to_challenge: The default belief the video will overturn
- core_mechanism: Why the thesis is true at a mechanism level

Argument Safety Rules:
- safe_claims: Claims the script can state directly (must have supporting proof)
- unsafe_claims: Claims that should not be presented as settled fact
- Every claim_id, proof_id, counterargument_id, beat_id must be unique

Beat Plan:
Map narrative beats to claim_ids and proof_anchors:
- Hook: Grab attention, establish the belief to challenge
- Reframe: Present the thesis and core mechanism
- Proof: Support with evidence anchors
- Close: Reinforce takeaway and CTA

Output format:

---
# ANGLE SELECTION
angle_id: (unique identifier, e.g., angle_1)
target_audience: (specific audience for this angle)
viewer_problem: (what problem the viewer has)
core_promise: (what they will get from watching)
primary_takeaway: (the one specific thing they should remember)
lens: (editorial lens: use format library name)
format: (delivery format: talking head, screen recording, etc.)
tone: (tone: direct, conversational, urgent, playful, etc.)
cta: (call to action)
why_this_version_should_exist: (why this angle is different from what exists)
differentiation_summary: (why this angle is distinct from baseline market framing)
market_framing_challenged: (common framing this angle reframes or contradicts)
genericity_risks:
- (specific failure mode to avoid)
selection_reasoning: (why this angle was chosen)

# THESIS
thesis: (one-sentence expert argument)
audience_belief_to_challenge: (default belief to overturn)
core_mechanism: (mechanism-level explanation of why thesis is true)

# PROOF ANCHORS
proof_anchors:
---
proof_id: proof_1
summary: (grounded evidence or observation from research)
source_ids: src_01, src_02
usage_note: (how the script should use this proof)
---

# COUNTERARGUMENTS
counterarguments:
---
counterargument_id: counter_1
counterargument: (credible pushback or caveat)
response: (how the script should answer it)
response_proof_ids: proof_1
---

# SAFE CLAIMS
safe_claims:
---
claim_id: claim_1
claim: (claim the script can safely state)
supporting_proof_ids: proof_1
note: (optional scope or framing note)
---

# UNSAFE CLAIMS
unsafe_claims:
---
claim_id: claim_unsafe_1
claim: (claim that should be avoided or heavily qualified)
supporting_proof_ids: proof_1
note: (why it is unsafe)
---

# BEAT PLAN
beat_claim_plan:
---
beat_id: beat_1
beat_name: Hook | Reframe | Proof | Close
goal: (what this beat must accomplish)
claim_ids: claim_1
proof_anchor_ids: proof_1
counterargument_ids:
transition_note: (how this beat moves into the next)
---

# DIFFERENTIATION
what_this_contributes: (what this angle contributes beyond consensus or standard advice)
genericity_flags:
- (specific generic framing to avoid)
- (another framing to avoid)
differentiation_stategy: (how this piece stands out from market-standard content)
---"""


def thesis_user(
    item: BacklogItem,
    strategy: StrategyMemory,
    research_pack: ResearchPack | None = None,
) -> str:
    """Build the user prompt for thesis generation.

    Args:
        item: The backlog item (idea) to develop into a thesis
        strategy: Strategy memory for brand/audience guidance
        research_pack: Optional research pack providing evidence context
    """
    parts = [
        f"Idea: {item.idea}",
        f"Audience: {item.audience}",
    ]

    if item.problem:
        parts.append(f"Problem framing: {item.problem}")

    if strategy:
        if strategy.positioning:
            parts.append(f"Brand positioning: {strategy.positioning}")
        if strategy.tone_rules:
            parts.append(f"Tone rules: {', '.join(strategy.tone_rules)}")
        if strategy.proof_standards:
            parts.append(f"Proof standards: {strategy.proof_standards}")

    if research_pack:
        parts.append("\n=== RESEARCH CONTEXT ===")
        if research_pack.key_facts:
            parts.append("Key facts:\n- " + "\n- ".join(research_pack.key_facts[:5]))
        if research_pack.proof_points:
            parts.append("Proof points:\n- " + "\n- ".join(research_pack.proof_points[:5]))
        if research_pack.audience_insights:
            parts.append(
                "Audience insights:\n- " + "\n- ".join(research_pack.audience_insights[:3])
            )
        if research_pack.examples:
            parts.append("Examples:\n- " + "\n- ".join(research_pack.examples[:3]))
        if research_pack.case_studies:
            parts.append("Case studies:\n- " + "\n- ".join(research_pack.case_studies[:2]))
        if research_pack.gaps_to_exploit:
            parts.append("Competitor gaps:\n- " + "\n- ".join(research_pack.gaps_to_exploit[:2]))
        if research_pack.unsafe_or_uncertain_claims:
            parts.append(
                "Unsafe/uncertain claims to avoid:\n- "
                + "\n- ".join(research_pack.unsafe_or_uncertain_claims[:3])
            )
        if research_pack.claims_requiring_verification:
            parts.append(
                "Claims requiring verification:\n- "
                + "\n- ".join(research_pack.claims_requiring_verification[:3])
            )

    return "\n\n".join(parts)
