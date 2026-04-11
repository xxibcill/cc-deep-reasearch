"""Prompt templates for the research pack builder.

Contract Version: 1.1.0

Parser expectations:
- synthesis output: Prefers structured sections named findings, claims,
  counterpoints, uncertainty_flags, assets_needed, and research_stop_reason.
  Structured sections use repeated `---` blocks with scalar fields and may
  reference source_ids from the prompt-provided source catalog.
- The parser remains tolerant of older legacy list sections so downstream
  stages can continue operating during contract migration.

When editing prompts, ensure output format remains compatible with
the parser in agents/research_pack.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import AngleOption, BacklogItem

CONTRACT_VERSION = "1.1.0"

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
Using the source catalog provided, extract a focused research pack.
Do not over-research. Stop when these conditions are all met:
- You have 3-7 useful proof points
- You have identified 1-2 gaps in competitor coverage
- You can support the main promise
- You have flagged uncertain claims
- You can point each major finding or claim to one or more source_ids when possible

Rules:
- Use source_ids from the source catalog whenever a finding or claim has support
- Do not invent source_ids
- If a source is weak or indirect, lower confidence or move the idea into uncertainty_flags
- Keep findings concrete and compact
- Use counterpoints for caveats, limits, or credible pushback
- Keep assets_needed as a simple list

Output format:

findings:
---
finding_type: audience_insight | competitor_observation | example | case_study | gap_to_exploit
summary: (finding summary)
source_ids: src_a, src_b
confidence: high | medium | low | unknown
evidence_note: (optional note)
---

claims:
---
claim_type: key_fact | proof_point
claim: (claim text)
source_ids: src_a, src_b
confidence: high | medium | low | unknown
mechanism: (optional mechanism or why it matters)
---

counterpoints:
---
summary: (counterpoint or caveat)
why_it_matters: (why the team should care)
source_ids: src_a
confidence: high | medium | low | unknown
---

assets_needed:
- (asset 1)

uncertainty_flags:
---
flag_type: verification_required | unsafe_or_uncertain
claim: (claim text)
reason: (why it is uncertain or risky)
severity: low | medium | high
source_ids: src_a
---

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
