"""Prompt templates for the research pack builder."""

from __future__ import annotations

from cc_deep_research.content_gen.models import AngleOption, BacklogItem

GLOBAL_RULES = """\
You are building a compact research pack for a short-form video inside a modular workflow.

Important:
- Only do the task for this step
- Keep research sufficient, not exhaustive
- Never invent facts, examples, or proof
- When evidence is weak, say so
- Flag uncertain claims explicitly
- Stop when you have enough to support the content"""


SYNTHESIS_SYSTEM = f"""\
{GLOBAL_RULES}

You are synthesizing search results into a compact research pack.

Task:
Using the search results provided, extract a focused research pack.
Do not over-research. Stop when these conditions are all met:
- You have 3-7 useful proof points
- You have identified 1-2 gaps in competitor coverage
- You can support the main promise
- You have flagged uncertain claims

Output format:

audience_insights:
- (insight 1)
- (insight 2)

competitor_observations:
- (observation 1)
- (observation 2)

key_facts:
- (fact 1)
- (fact 2)

proof_points:
- (proof 1)
- (proof 2)

examples:
- (example 1)

case_studies:
- (case study if found)

gaps_to_exploit:
- (gap 1)
- (gap 2)

assets_needed:
- (asset 1)

claims_requiring_verification:
- (claim 1)

unsafe_or_uncertain_claims:
- (claim 1)

research_stop_reason: (why research is sufficient)"""


def synthesis_user(
    item: BacklogItem,
    angle: AngleOption,
    search_context: str,
    *,
    feedback: str = "",
) -> str:
    parts = [
        f"Idea: {item.idea}",
        f"Core Promise: {angle.core_promise}",
        f"Target Audience: {angle.target_audience}",
        f"Viewer Problem: {angle.viewer_problem}",
        f"\nSearch results:\n{search_context}",
    ]
    if feedback:
        parts.append(f"\nPrevious iteration feedback to address:\n{feedback}")
    return "\n".join(parts)
