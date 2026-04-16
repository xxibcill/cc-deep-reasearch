"""Prompt templates for the research pack builder.

Contract Version: 1.3.0

P3-T1: Added research depth routing metadata to track which tier was used
and why, making the pipeline's research investment visible in traces.

Parser expectations:
- synthesis output: Prefers structured sections named findings, claims,
  counterpoints, uncertainty_flags, assets_needed, and research_stop_reason.
  Structured sections use repeated `---` blocks with scalar fields and may
  reference source_ids from the prompt-provided source catalog.
- The parser remains tolerant of older legacy list sections so downstream
  stages can continue operating during contract migration.
- Hypothesis tracking: The synthesis should explicitly address each hypothesis
  from the opportunity brief and note whether it is supported, unsupported,
  or unresolved by the gathered evidence.

When editing prompts, ensure output format remains compatible with
the parser in agents/research_pack.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import AngleOption, BacklogItem

CONTRACT_VERSION = "1.3.0"

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

Source Quality Guidelines:
The source catalog is pre-sorted by evidence strength (strongest first).
Each source carries explicit quality signals:
- authority: primary (official docs/data) > secondary (news/analysis) > tertiary (summaries/social)
- directness: direct (original data) > indirect (analysis) > anecdotal (personal accounts)
- freshness: current (>6mo) > recent (>2yr) > stale
- quality rank: 0-1 score combining all signals (higher = stronger)

Evidence Preference Rules:
- When multiple sources cover the same claim, prefer sources with higher quality_rank
- For key facts and proof points, prefer authority=primary and directness=direct
- If only weak sources (quality_rank < 0.5) are available for a claim, flag the claim
  in uncertainty_flags with severity=high and note the weak support
- Secondary and tertiary sources are acceptable for context and framing, but
  anchor claims should cite primary sources
- Stale sources (>2yr) may still be valid for foundational facts but should be
  flagged if the topic is fast-moving

Rules:
- Use source_ids from the source catalog whenever a finding or claim has support
- Do not invent source_ids
- If a source is weak or indirect, lower confidence or move the idea into uncertainty_flags
- Keep findings concrete and compact
- Use counterpoints for caveats, limits, or credible pushback
- Keep assets_needed as a simple list

Hypothesis Testing (if hypotheses are provided):
- For each hypothesis, evaluate whether the gathered evidence supports,
  contradicts, or is inconclusive about the claim
- Record the hypothesis verdict in the findings or claims section with
  a confidence level reflecting the evidence strength
- Flag any hypothesis with insufficient evidence or contradictory signals

Output format:

findings:
---
finding_type: audience_insight | competitor_observation | example | case_study | gap_to_exploit
summary: (finding summary)
source_ids: src_a, src_b
confidence: high | medium | low | unknown
evidence_note: (optional note)
hypothesis_verdict: (optional: supported | unsupported | unresolved — only if hypotheses were provided)
---

claims:
---
claim_type: key_fact | proof_point
claim: (claim text)
source_ids: src_a, src_b
confidence: high | medium | low | unknown
mechanism: (optional mechanism or why it matters)
hypothesis_verdict: (optional: supported | unsupported | unresolved — only if hypotheses were provided)
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
    research_hypotheses: list[str] | None = None,
) -> str:
    parts = [
        f"Idea: {item.idea}",
        f"Core Promise: {angle.core_promise}",
        f"Target Audience: {angle.target_audience}",
        f"Viewer Problem: {angle.viewer_problem}",
        f"\nSearch results:\n{search_context}",
    ]
    if research_hypotheses:
        parts.append("\nResearch hypotheses to test:\n- " + "\n- ".join(research_hypotheses))
    if feedback:
        parts.append(f"\nPrevious iteration feedback to address:\n{feedback}")
    return "\n".join(parts)
