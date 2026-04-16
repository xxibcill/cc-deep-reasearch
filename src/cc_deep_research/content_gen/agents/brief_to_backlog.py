"""Brief-to-backlog generation agent.

Generates backlog item candidates from an approved brief revision.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import BriefRevision
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_brief_to_backlog"


class GeneratedBacklogItem(BaseModel):
    """A single backlog item generated from a brief."""

    title: str = ""
    one_line_summary: str = ""
    raw_idea: str = ""
    constraints: str = ""
    category: str = "authority-building"
    audience: str = ""
    problem: str = ""
    emotional_driver: str = ""
    urgency_level: str = "medium"
    why_now: str = ""
    hook: str = ""
    content_type: str = ""
    key_message: str = ""
    call_to_action: str = ""
    evidence: str = ""
    risk_level: str = "medium"
    source_theme: str = ""
    reason: str = ""


class BriefToBacklogResponse(BaseModel):
    """Structured response from brief-to-backlog generation."""

    reply_markdown: str
    items: list[GeneratedBacklogItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """\
You are a creative content strategist turning opportunity briefs into concrete backlog items.

Your task:
1. Read the opportunity brief revision carefully
2. Extract the core content angle, audience, and key message
3. Generate 3-5 specific backlog item candidates that operationalize the brief
4. Each item should be a distinct content piece that could stand on its own

Important constraints:
- Be specific and concrete — avoid generic titles
- Each item should target a distinct angle, format, or audience segment from the brief
- Items should be actionable — a writer could start from these alone
- Return JSON only — no prose outside the JSON structure

Output format — return ONLY this JSON structure:

{
  "reply_markdown": "I found 5 strong angles from this brief...",
  "items": [
    {
      "title": "Specific, concrete title for this content piece",
      "one_line_summary": "One sentence that captures the unique angle",
      "raw_idea": "Initial thinking / working notes (optional)",
      "constraints": "Any constraints or must-avoid topics",
      "category": "authority-building|trend-responsive|evergreen",
      "audience": "Who is this specifically for",
      "problem": "The specific problem this content solves",
      "emotional_driver": "What emotional need does this address",
      "urgency_level": "low|medium|high",
      "why_now": "Why this angle is relevant right now",
      "hook": "The hook that will grab attention",
      "content_type": "short-form-video|carouselpost|longform-article|etc",
      "key_message": "The single key takeaway",
      "call_to_action": "What the viewer/reader should do next",
      "evidence": "What proof or social proof to include",
      "risk_level": "low|medium|high",
      "source_theme": "The brief theme this came from",
      "reason": "Why this angle was chosen from the brief"
    }
  ],
  "warnings": ["any concerns about the generated items"]
}"""


def _build_user_prompt(brief_revision: BriefRevision) -> str:
    """Build the user prompt with brief content."""
    parts = ["=== OPPORTUNITY BRIEF ===", ""]

    if brief_revision.theme:
        parts.append(f"Theme: {brief_revision.theme}")
    if brief_revision.goal:
        parts.append(f"Goal: {brief_revision.goal}")
    if brief_revision.primary_audience_segment:
        parts.append(f"Primary Audience: {brief_revision.primary_audience_segment}")
    if brief_revision.secondary_audience_segments:
        parts.append(f"Secondary Audiences: {', '.join(brief_revision.secondary_audience_segments)}")
    if brief_revision.problem_statements:
        parts.append("")
        parts.append("Problem Statements:")
        for ps in brief_revision.problem_statements:
            parts.append(f"  - {ps}")
    if brief_revision.content_objective:
        parts.append(f"Content Objective: {brief_revision.content_objective}")
    if brief_revision.sub_angles:
        parts.append("")
        parts.append(f"Sub-Angles to Explore: {', '.join(brief_revision.sub_angles)}")
    if brief_revision.success_criteria:
        parts.append("")
        parts.append("Success Criteria:")
        for sc in brief_revision.success_criteria:
            parts.append(f"  - {sc}")
    if brief_revision.expert_take:
        parts.append(f"Expert Take: {brief_revision.expert_take}")
    if brief_revision.platform_constraints:
        parts.append("")
        parts.append(f"Platform Constraints: {', '.join(brief_revision.platform_constraints)}")
    if brief_revision.risk_constraints:
        parts.append(f"Risk Constraints: {', '.join(brief_revision.risk_constraints)}")

    parts.append("")
    parts.append("Generate backlog item candidates from this brief.")

    return "\n".join(parts)


async def generate_backlog_from_brief(
    brief_revision: BriefRevision,
    config: Config | None = None,
) -> BriefToBacklogResponse:
    """Generate backlog item candidates from a brief revision.

    Args:
        brief_revision: The brief revision to operationalize
        config: Optional configuration

    Returns:
        BriefToBacklogResponse with generated items and metadata
    """
    if config is None:
        from cc_deep_research.config import load_config

        config = load_config()

    from cc_deep_research.llm.registry import LLMRouteRegistry

    registry = LLMRouteRegistry(config.llm)
    router = LLMRouter(registry)

    user_prompt = _build_user_prompt(brief_revision)

    try:
        text = await call_agent_llm_text(
            router=router,
            agent_id=AGENT_ID,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.6,
            workflow_name="brief to backlog",
            cli_command="content-gen brief-to-backlog",
            logger=logger,
            allow_blank=False,
        )

        parsed = _parse_response(text, brief_revision.theme or "")
        return parsed

    except Exception as exc:
        logger.warning("Brief-to-backlog LLM call failed: %s", exc)
        return BriefToBacklogResponse(
            reply_markdown="I had trouble generating backlog items from this brief.",
            items=[],
            warnings=[f"LLM call failed: {exc}"],
        )


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Extract JSON object from text, handling code fences and partial output."""
    text = text.strip()

    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    fence_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
    for match in fence_pattern.finditer(text):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # Try finding a JSON object anywhere in the text
    json_start = text.find("{")
    if json_start != -1:
        depth = 0
        for i, ch in enumerate(text[json_start:], start=json_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[json_start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    return None


def _parse_response(text: str, source_theme: str) -> BriefToBacklogResponse:
    """Parse LLM output into BriefToBacklogResponse."""
    parsed = _extract_json_from_text(text)
    if parsed is None:
        return BriefToBacklogResponse(
            reply_markdown=text.strip()[:500] if text.strip() else "No items generated.",
            items=[],
            warnings=["Failed to parse structured output from LLM"],
        )

    raw_items = parsed.get("items", [])
    validated_items: list[GeneratedBacklogItem] = []

    for item_data in raw_items:
        if not isinstance(item_data, dict):
            continue

        title = str(item_data.get("title", "")).strip()
        if not title:
            continue

        validated_items.append(
            GeneratedBacklogItem(
                title=title[:200],
                one_line_summary=str(item_data.get("one_line_summary", ""))[:300],
                raw_idea=str(item_data.get("raw_idea", ""))[:1000],
                constraints=str(item_data.get("constraints", ""))[:500],
                category=str(item_data.get("category", "authority-building"))[:50],
                audience=str(item_data.get("audience", ""))[:300],
                problem=str(item_data.get("problem", ""))[:500],
                emotional_driver=str(item_data.get("emotional_driver", ""))[:300],
                urgency_level=str(item_data.get("urgency_level", "medium"))[:20],
                why_now=str(item_data.get("why_now", ""))[:500],
                hook=str(item_data.get("hook", ""))[:300],
                content_type=str(item_data.get("content_type", ""))[:50],
                key_message=str(item_data.get("key_message", ""))[:500],
                call_to_action=str(item_data.get("call_to_action", ""))[:300],
                evidence=str(item_data.get("evidence", ""))[:500],
                risk_level=str(item_data.get("risk_level", "medium"))[:20],
                source_theme=source_theme,
                reason=str(item_data.get("reason", ""))[:500],
            )
        )

    return BriefToBacklogResponse(
        reply_markdown=str(parsed.get("reply_markdown", ""))[:500] or "Generated items.",
        items=validated_items,
        warnings=list(parsed.get("warnings", []))[:10],
    )
