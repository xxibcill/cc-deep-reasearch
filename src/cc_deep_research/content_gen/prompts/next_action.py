"""Prompt templates for the next-action recommendation agent."""

from __future__ import annotations

from cc_deep_research.content_gen.models import BacklogItem

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are a superuser editorial assistant for a short-form video content backlog.

Important:
- Be precise and actionable
- Keep the tone analytical and operator-focused
- Always explain the 'why' behind your recommendation
- Return JSON only — no prose outside the JSON structure"""


NEXT_ACTION_SYSTEM = f"""\
{GLOBAL_RULES}

You analyze a single backlog item and recommend what the operator should do next.

Recommendation types:
- produce: Item is ready to move into the production pipeline
- reframe: Item needs sharper problem framing, better hook, or clearer audience
- gather_evidence: Item is conceptually sound but needs proof/evidence
- hold: Item is not ready but shouldn't be archived — wait for more context
- archive: Item is stale, redundant, or clearly wrong for the channel

Rules:
- Prefer produce/reframe/gather_evidence over hold/archive
- Be specific about what fields are weak and why
- Identify concrete blockers (missing evidence, weak hook, unclear audience, etc.)
- Keep rationale concise — 1-3 sentences
- Confidence reflects how certain you are: high (>0.8) = strong signal, low (<0.5) = uncertain

Output format — return ONLY this JSON structure, no additional text:

{{
  "action": "produce|reframe|gather_evidence|hold|archive",
  "rationale": "Why this action is recommended (1-3 sentences)",
  "confidence": 0.0-1.0,
  "blockers": ["specific gap 1", "specific gap 2"],
  "suggested_fields": {{ "field_name": "what to write or improve" }}
}}

If confidence is low (<0.5), prefer 'hold' or 'gather_evidence' over strong actions."""


def build_next_action_user(
    item: BacklogItem,
    strategy: dict | None = None,
) -> str:
    """Build the user prompt for next-action analysis."""
    parts = ["=== BACKLOG ITEM TO ANALYZE ==="]

    parts.append(f"idea_id: {item.idea_id}")
    parts.append(f"title: {item.title or item.idea}")
    parts.append(f"one_line_summary: {item.one_line_summary or item.idea}")
    parts.append(f"raw_idea: {item.raw_idea or '(not set)'}")
    parts.append(f"constraints: {item.constraints or '(not set)'}")
    parts.append(f"category: {item.category}")
    parts.append(f"audience: {item.audience or '(not set)'}")
    parts.append(f"persona_detail: {item.persona_detail or '(not set)'}")
    parts.append(f"problem: {item.problem or '(not set)'}")
    parts.append(f"emotional_driver: {item.emotional_driver or '(not set)'}")
    parts.append(f"urgency_level: {item.urgency_level or '(not set)'}")
    parts.append(f"why_now: {item.why_now or '(not set)'}")
    parts.append(f"hook: {item.hook or item.potential_hook or '(not set)'}")
    parts.append(f"evidence: {item.evidence or '(not set)'}")
    parts.append(f"content_type: {item.content_type or '(not set)'}")
    parts.append(f"format_duration: {item.format_duration or '(not set)'}")
    parts.append(f"key_message: {item.key_message or '(not set)'}")
    parts.append(f"call_to_action: {item.call_to_action or '(not set)'}")
    parts.append(f"status: {item.status}")
    parts.append(f"risk_level: {item.risk_level}")
    parts.append(f"latest_score: {item.latest_score}")
    parts.append(f"latest_recommendation: {item.latest_recommendation or '(none)'}")
    parts.append(f"priority_score: {item.priority_score}")
    parts.append(f"selection_reasoning: {item.selection_reasoning or '(none)'}")
    parts.append(f"expertise_reason: {item.expertise_reason or '(none)'}")
    parts.append(f"genericity_risk: {item.genericity_risk or '(none)'}")
    parts.append(f"proof_gap_note: {item.proof_gap_note or '(none)'}")
    parts.append(f"source_theme: {item.source_theme or '(none)'}")
    parts.append(f"source: {item.source or '(none)'}")

    if strategy:
        parts.append("")
        parts.append("=== STRATEGY CONTEXT ===")
        if strategy.get("niche"):
            parts.append(f"Niche: {strategy['niche']}")
        if strategy.get("content_pillars"):
            parts.append(f"Content pillars: {', '.join(strategy['content_pillars'])}")

    parts.append("")
    parts.append("Provide your recommendation as JSON only.")

    return "\n".join(parts)
