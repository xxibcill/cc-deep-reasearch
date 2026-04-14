"""Prompt templates for the execution brief agent."""

from __future__ import annotations

from cc_deep_research.content_gen.models import BacklogItem

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are a superuser editorial assistant for a short-form video content backlog.

Important:
- Be specific and actionable
- Keep the brief concise and operator-friendly
- Ground everything in the item's existing metadata
- Return JSON only — no prose outside the JSON structure"""


EXECUTION_BRIEF_SYSTEM = f"""\
{GLOBAL_RULES}

You generate a production-readiness brief for a backlog item that is strong enough
to move toward the production pipeline. The goal is to reduce manual setup work
before the pipeline starts.

The brief should cover:
- audience and problem framing: who is this for and what tension does it resolve?
- hook direction: what is the single strongest angle to open with?
- evidence requirements: what proof/data/examples does this need to be credible?
- proof gaps: what is currently missing or weak?
- research questions: what needs to be verified or deepened before production?
- risks before production: what could go wrong or get the creator in trouble?

Rules:
- Be specific about what evidence is needed — not just "add evidence"
- Identify the single strongest hook direction, not a menu of options
- Flag any generic or clichéd framings that would make the content blend in
- Keep research questions focused on what would block production
- If the item is not yet ready for production, say so and explain why

Output format — return ONLY this JSON structure, no additional text:

{{
  "audience": "Target audience in 1-2 sentences",
  "problem_statement": "Core problem/tension in 1-2 sentences",
  "hook_direction": "Single strongest hook angle in 1-2 sentences",
  "evidence_requirements": ["specific proof point 1", "specific proof point 2"],
  "proof_gaps": ["specific gap 1", "specific gap 2"],
  "research_questions": ["specific question 1", "specific question 2"],
  "risks_before_production": ["specific risk 1", "specific risk 2"],
  "is_ready_for_production": true|false,
  "readiness_summary": "One-sentence summary of readiness"
}}

Be concise and specific. Do not repeat information across fields."""


def build_execution_brief_user(
    item: BacklogItem,
    strategy: dict | None = None,
) -> str:
    """Build the user prompt for execution brief generation."""
    parts = ["=== BACKLOG ITEM ==="]

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
    parts.append(f"production_status: {item.production_status}")
    parts.append(f"risk_level: {item.risk_level}")
    parts.append(f"latest_score: {item.latest_score}")
    parts.append(f"latest_recommendation: {item.latest_recommendation or '(none)'}")
    parts.append(f"selection_reasoning: {item.selection_reasoning or '(none)'}")
    parts.append(f"expertise_reason: {item.expertise_reason or '(none)'}")
    parts.append(f"genericity_risk: {item.genericity_risk or '(none)'}")
    parts.append(f"proof_gap_note: {item.proof_gap_note or '(none)'}")
    parts.append(f"source_theme: {item.source_theme or '(none)'}")
    parts.append(f"source: {item.source or '(none)'}")

    # Scoring metadata
    parts.append("")
    parts.append("=== SCORING CONTEXT ===")
    parts.append(f"priority_score: {item.priority_score}")
    if item.last_scored_at:
        parts.append(f"last_scored_at: {item.last_scored_at}")

    if strategy:
        parts.append("")
        parts.append("=== STRATEGY CONTEXT ===")
        if strategy.get("niche"):
            parts.append(f"Niche: {strategy['niche']}")
        if strategy.get("content_pillars"):
            parts.append(f"Content pillars: {', '.join(strategy['content_pillars'])}")
        if strategy.get("proof_standards"):
            parts.append(f"Proof standards: {', '.join(strategy['proof_standards'][:3])}")

    parts.append("")
    parts.append("Generate the production-readiness brief as JSON only.")

    return "\n".join(parts)
