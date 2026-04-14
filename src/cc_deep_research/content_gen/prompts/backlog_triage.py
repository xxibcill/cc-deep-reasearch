"""Prompt templates for the backlog batch triage agent.

Contract Version: 1.0.0

The agent analyzes the backlog and proposes batch operations for:
- batch_enrich: upgrade sparse/weak items with enrichment fields
- batch_reframe: improve vague or generic ideas
- dedupe_recommendation: identify and merge duplicate/near-duplicate items
- archive_recommendation: flag items that should be archived
- priority_recommendation: suggest priority score or recommendation changes

Output format: JSON only (see agents/backlog_triage.py for parsing contract).
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import BacklogItem

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are a superuser editorial assistant for a short-form video content backlog.

Important:
- Be precise and actionable
- Keep the tone analytical and operator-focused
- Prefer enriching or reframing over deleting
- Return JSON only — no prose outside the JSON structure"""


BACKLOG_TRIAGE_SYSTEM = f"""\
{GLOBAL_RULES}

You are analyzing a backlog for a superuser operator who wants to clean up and
enrich the backlog in batch.

Your task:
1. Read the backlog items carefully
2. Identify items that are sparse, duplicate, weak, or missing key fields
3. Group related items into proposals
4. For each proposal, provide a clear reason and the specific changes needed

Proposal types:
- batch_enrich: Add missing fields (why_now, potential_hook, evidence, proof_gap_note, genericity_risk)
  to items that are thin on editorial detail. Prefer enriching over archiving.
- batch_reframe: Improve vague or generic ideas by sharpening the problem statement,
  audience definition, or hook. Target items with weak idea/problem/hook fields.
- dedupe_recommendation: Identify items that cover the same topic or audience.
  Specify a preferred_idea_id to keep and reason why. Do NOT auto-delete — just recommend.
- archive_recommendation: Flag items that are stale, redundant, or clearly wrong for the
  channel. Always prefer reframe or enrich over archive unless the item is clearly dead.
- priority_recommendation: Suggest changes to priority_score or latest_recommendation
  based on timeliness, evidence strength, or strategic fit.

Rules:
- Never propose deletion — only archive
- Always prefer enrich or reframe over archive
- batch_enrich targets items with fewer than 2 of: evidence, why_now, potential_hook
- batch_reframe targets items with fewer than 2 of: idea, problem, potential_hook
- dedupe must always specify preferred_idea_id and a reason
- Be specific: include exact field values in proposals
- If an item already has strong editorial content, do not propose overwriting it

Output format — return ONLY this JSON structure, no additional text:

{{
  "reply_markdown": "Summary of what you found and what you're proposing...",
  "proposals": [
    {{
      "kind": "batch_enrich|batch_reframe|dedupe_recommendation|archive_recommendation|priority_recommendation",
      "idea_ids": ["id1", "id2"],
      "reason": "Why this proposal is needed",
      "fields": {{ "field_name": "proposed_value" }},
      "preferred_idea_id": "id_to_keep"  // only for dedupe_recommendation
    }}
  ],
  "warnings": ["any concerns about the proposals"],
  "mentioned_idea_ids": ["id1", "id2"]
}}

If no proposals are warranted, return proposals=[] and a brief explanation."""


def build_triage_user(
    backlog_items: list[BacklogItem],
    strategy: dict | None = None,
    analysis_context: dict | None = None,
) -> str:
    """Build the user prompt for the backlog triage agent.

    Args:
        backlog_items: Current backlog snapshot
        strategy: Optional strategy context
        analysis_context: Optional pre-computed analysis from batch_analysis module
    """
    parts = ["=== BACKLOG TO ANALYZE ==="]

    if not backlog_items:
        parts.append("(empty backlog)")
    else:
        for item in backlog_items:
            parts.append("---")
            parts.append(f"idea_id: {item.idea_id}")
            parts.append(f"category: {item.category}")
            parts.append(f"idea: {item.idea}")
            parts.append(f"audience: {item.audience}")
            parts.append(f"problem: {item.problem}")
            parts.append(f"status: {item.status}")
            if item.production_status and item.production_status != "idle":
                parts.append(f"production_status: {item.production_status}")
            if item.latest_score is not None:
                parts.append(f"score: {item.latest_score}")
            if item.latest_recommendation:
                parts.append(f"recommendation: {item.latest_recommendation}")
            if item.why_now:
                parts.append(f"why_now: {item.why_now}")
            if item.potential_hook:
                parts.append(f"hook: {item.potential_hook}")
            if item.evidence:
                parts.append(f"evidence: {item.evidence}")
            if item.proof_gap_note:
                parts.append(f"proof_gap: {item.proof_gap_note}")
            if item.genericity_risk:
                parts.append(f"genericity_risk: {item.genericity_risk}")
            if item.selection_reasoning:
                parts.append(f"reasoning: {item.selection_reasoning}")

    # Include heuristic analysis results
    if analysis_context:
        parts.append("")
        parts.append("=== HEURISTIC ANALYSIS (for your reference) ===")

        # Duplicate candidates
        dupes = analysis_context.get("duplicate_candidates", [])
        if dupes:
            parts.append(f"\nDuplicate candidates found ({len(dupes)} pairs):")
            for d in dupes[:10]:  # Limit to first 10
                score = d.get("score", 0)
                preferred = d.get("preferred_id", "")
                parts.append(
                    f"  - {d['idea_id_a']} <-> {d['idea_id_b']} "
                    f"(similarity={score:.2f}, prefer={preferred})"
                )

        # Sparse items
        sparse = analysis_context.get("sparse_items", [])
        if sparse:
            parts.append(f"\nSparse items needing enrichment ({len(sparse)} items):")
            for s in sparse[:10]:
                parts.append(
                    f"  - {s['idea_id']}: score={s['score']:.1f}, "
                    f"missing={s['missing_fields']}"
                )

        # Gaps
        gaps = analysis_context.get("gaps", [])
        if gaps:
            parts.append(f"\nGap analysis ({len(gaps)} gaps found):")
            for g in gaps:
                parts.append(f"  - [{g['gap_type']}] {g['description']}")
                parts.append(f"    Suggestion: {g['suggestion']}")

        # Theme clusters
        clusters = analysis_context.get("theme_clusters", {})
        if clusters:
            parts.append(f"\nTheme distribution: {clusters}")

    if strategy:
        parts.append("")
        parts.append("=== STRATEGY ===")
        if strategy.get("niche"):
            parts.append(f"Niche: {strategy['niche']}")
        if strategy.get("content_pillars"):
            parts.append(f"Content pillars: {', '.join(strategy['content_pillars'])}")

    parts.append("")
    parts.append("Provide your response as JSON only.")

    return "\n".join(parts)
