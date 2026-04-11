"""Prompt templates for the argument map builder.

Contract Version: 1.0.0

Parser expectations:
- The response must provide scalar fields named thesis,
  audience_belief_to_challenge, and core_mechanism.
- The response must provide named sections proof_anchors, counterarguments,
  safe_claims, unsafe_claims, and beat_claim_plan.
- Each structured section uses repeated `---` blocks with scalar fields.
- proof_id, claim_id, counterargument_id, and beat_id values must be explicit
  strings because downstream parsing validates cross-references.

When editing prompts, ensure output format remains compatible with
the parser in agents/argument_map.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import AngleOption, BacklogItem, ResearchPack

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are building the argument map that bridges research into script drafting.

Important:
- Only do the task for this step
- Stay grounded in the provided research pack
- Do not invent proof, statistics, or case studies
- Separate safe claims from unsafe claims
- Use explicit IDs exactly as requested so the parser can validate references
- Keep the output compact and operational for downstream script planning"""


ARGUMENT_MAP_SYSTEM = f"""\
{GLOBAL_RULES}

Task:
Turn the selected idea, chosen angle, and structured research pack into a
precise argument map for a short-form video.

Rules:
- The thesis should make one clear expert point, not a topic label
- audience_belief_to_challenge should state the default belief the video will overturn
- core_mechanism should explain why the thesis is true at a mechanism level
- proof_anchors should only contain support grounded in the provided research pack
- safe_claims are claims the script can say directly
- unsafe_claims are tempting claims that should not be presented as settled fact
- beat_claim_plan should map the narrative beats to claim_ids and proof_ids
- Every claim_id, proof_id, counterargument_id, and beat_id must be unique
- If a beat uses no counterargument, leave counterargument_ids blank after the colon

Task 19 — Competitive Differentiation Check:
After the argument map sections above, explicitly state:
- what_this_contributes: What this angle contributes beyond consensus or standard advice
  (e.g., "Most content says X, but this angle shows Y by explaining Z mechanism")
- genericity_flags: Specific generic or clichéd framings this script must avoid
  (e.g., "Don't just say 'hard work pays off' — everyone says that without backing")
- differentiation_strategy: How this piece will stand out from market-standard
  content on the same topic (specific mechanism, contrarian framing, data depth, etc.)

Output format:

thesis: (one-sentence argument)
audience_belief_to_challenge: (belief to overturn)
core_mechanism: (mechanism-level explanation)

proof_anchors:
---
proof_id: proof_1
summary: (grounded evidence or observation)
source_ids: src_01, src_02
usage_note: (how the script should use this proof)
---

counterarguments:
---
counterargument_id: counter_1
counterargument: (credible pushback or caveat)
response: (how the script should answer it)
response_proof_ids: proof_1
---

safe_claims:
---
claim_id: claim_1
claim: (claim the script can safely state)
supporting_proof_ids: proof_1
note: (optional note about scope or framing)
---

unsafe_claims:
---
claim_id: claim_unsafe_1
claim: (claim that should be avoided or heavily qualified)
supporting_proof_ids: proof_1
note: (why it is unsafe)
---

beat_claim_plan:
---
beat_id: beat_1
beat_name: Hook | Reframe | Proof | Close
goal: (what this beat must accomplish)
claim_ids: claim_1
proof_anchor_ids: proof_1
counterargument_ids:
transition_note: (how this beat should move into the next one)
---

what_this_contributes: (what this angle contributes beyond consensus or standard advice)
genericity_flags:
- (specific generic or clichéd framing to avoid)
- (another framing to avoid)
differentiation_strategy: (how this piece stands out from market-standard content)"""


def argument_map_user(
    item: BacklogItem,
    angle: AngleOption,
    research_pack: ResearchPack,
) -> str:
    return "\n\n".join(
        [
            _render_selected_context(item, angle),
            _render_research_pack(research_pack),
        ]
    )


def _render_selected_context(item: BacklogItem, angle: AngleOption) -> str:
    return "\n".join(
        [
            "Selected Content Context:",
            f"Idea ID: {item.idea_id or 'unknown'}",
            f"Idea: {item.idea}",
            f"Audience: {item.audience}",
            f"Problem: {item.problem}",
            f"Angle ID: {angle.angle_id or 'unknown'}",
            f"Target Audience: {angle.target_audience}",
            f"Viewer Problem: {angle.viewer_problem}",
            f"Core Promise: {angle.core_promise}",
            f"Primary Takeaway: {angle.primary_takeaway}",
            f"Lens: {angle.lens}",
            f"Tone: {angle.tone}",
        ]
    )


def _render_research_pack(research_pack: ResearchPack) -> str:
    sections = [
        "Structured Research Pack:",
        _render_findings(research_pack),
        _render_claims(research_pack),
        _render_counterpoints(research_pack),
        _render_uncertainty_flags(research_pack),
    ]
    if research_pack.supporting_sources:
        sections.append(_render_supporting_sources(research_pack))
    return "\n\n".join(section for section in sections if section.strip())


def _render_findings(research_pack: ResearchPack) -> str:
    lines = ["findings:"]
    if not research_pack.findings:
        lines.append("- none")
        return "\n".join(lines)
    for finding in research_pack.findings:
        lines.extend(
            [
                "---",
                f"finding_id: {finding.finding_id}",
                f"finding_type: {finding.finding_type}",
                f"summary: {finding.summary}",
                f"source_ids: {', '.join(finding.source_ids)}",
                f"confidence: {finding.confidence}",
                f"evidence_note: {finding.evidence_note}",
            ]
        )
    return "\n".join(lines)


def _render_claims(research_pack: ResearchPack) -> str:
    lines = ["claims:"]
    if not research_pack.claims:
        lines.append("- none")
        return "\n".join(lines)
    for claim in research_pack.claims:
        lines.extend(
            [
                "---",
                f"claim_id: {claim.claim_id}",
                f"claim_type: {claim.claim_type}",
                f"claim: {claim.claim}",
                f"source_ids: {', '.join(claim.source_ids)}",
                f"confidence: {claim.confidence}",
                f"mechanism: {claim.mechanism}",
            ]
        )
    return "\n".join(lines)


def _render_counterpoints(research_pack: ResearchPack) -> str:
    lines = ["counterpoints:"]
    if not research_pack.counterpoints:
        lines.append("- none")
        return "\n".join(lines)
    for counterpoint in research_pack.counterpoints:
        lines.extend(
            [
                "---",
                f"counterpoint_id: {counterpoint.counterpoint_id}",
                f"summary: {counterpoint.summary}",
                f"why_it_matters: {counterpoint.why_it_matters}",
                f"source_ids: {', '.join(counterpoint.source_ids)}",
                f"confidence: {counterpoint.confidence}",
            ]
        )
    return "\n".join(lines)


def _render_uncertainty_flags(research_pack: ResearchPack) -> str:
    lines = ["uncertainty_flags:"]
    if not research_pack.uncertainty_flags:
        lines.append("- none")
        return "\n".join(lines)
    for flag in research_pack.uncertainty_flags:
        lines.extend(
            [
                "---",
                f"flag_id: {flag.flag_id}",
                f"flag_type: {flag.flag_type}",
                f"claim: {flag.claim}",
                f"reason: {flag.reason}",
                f"severity: {flag.severity}",
                f"source_ids: {', '.join(flag.source_ids)}",
            ]
        )
    return "\n".join(lines)


def _render_supporting_sources(research_pack: ResearchPack) -> str:
    lines = ["supporting_sources:"]
    for source in research_pack.supporting_sources:
        lines.extend(
            [
                "---",
                f"source_id: {source.source_id}",
                f"title: {source.title}",
                f"url: {source.url}",
                f"query_family: {source.query_family}",
                f"published_date: {source.published_date or 'unknown'}",
                f"snippet: {source.snippet}",
            ]
        )
    return "\n".join(lines)
