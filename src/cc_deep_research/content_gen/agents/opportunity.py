"""Opportunity planning agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import (
    OpportunityBrief,
    StrategyMemory,
)
from cc_deep_research.content_gen.prompts import opportunity as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_opportunity"
_REQUIRED_BRIEF_FIELDS = (
    ("Goal", "goal"),
    ("Primary audience segment", "primary_audience_segment"),
    ("Content objective", "content_objective"),
)


class OpportunityPlanningAgent:
    """Turn a raw theme into a structured opportunity brief."""

    def __init__(self, config: Config) -> None:
        from cc_deep_research.llm.registry import LLMRouteRegistry

        self._config = config
        registry = LLMRouteRegistry(config.llm)
        self._router = LLMRouter(registry)

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.5,
    ) -> str:
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="opportunity planning workflow",
            cli_command="content-gen pipeline",
            logger=logger,
        )

    async def plan(
        self,
        theme: str,
        strategy: StrategyMemory,
    ) -> OpportunityBrief:
        system = prompts.PLAN_OPPORTUNITY_SYSTEM
        user = prompts.plan_opportunity_user(theme, strategy)
        text = await self._call_llm(system, user, temperature=0.5)
        return _parse_opportunity_brief(text, theme)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_list_section(text: str, header: str) -> list[str]:
    items: list[str] = []
    in_section = False
    for line in text.split("\n"):
        stripped = line.strip()
        if header.lower() in stripped.lower():
            in_section = True
            continue
        if in_section:
            if stripped.startswith("- "):
                items.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("-"):
                break
    return items


def _parse_opportunity_brief(text: str, fallback_theme: str) -> OpportunityBrief:
    theme = _extract_field(text, "Theme") or fallback_theme
    goal = _extract_field(text, "Goal")
    primary_segment = _extract_field(text, "Primary audience segment")
    secondary_segments = _extract_list_section(text, "Secondary audience segments")
    problem_statements = _extract_list_section(text, "Problem statements")
    content_objective = _extract_field(text, "Content objective")
    proof_requirements = _extract_list_section(text, "Proof requirements")
    platform_constraints = _extract_list_section(text, "Platform constraints")
    risk_constraints = _extract_list_section(text, "Risk constraints")
    freshness = _extract_field(text, "Freshness rationale")
    sub_angles = _extract_list_section(text, "Sub-angles")
    hypotheses = _extract_list_section(text, "Research hypotheses")
    success_criteria = _extract_list_section(text, "Success criteria")

    brief = OpportunityBrief(
        theme=theme,
        goal=goal,
        primary_audience_segment=primary_segment,
        secondary_audience_segments=secondary_segments,
        problem_statements=problem_statements,
        content_objective=content_objective,
        proof_requirements=proof_requirements,
        platform_constraints=platform_constraints,
        risk_constraints=risk_constraints,
        freshness_rationale=freshness,
        sub_angles=sub_angles,
        research_hypotheses=hypotheses,
        success_criteria=success_criteria,
    )
    _validate_opportunity_brief(brief)
    return brief


def _validate_opportunity_brief(brief: OpportunityBrief) -> None:
    for label, field_name in _REQUIRED_BRIEF_FIELDS:
        value = getattr(brief, field_name)
        if value:
            continue
        msg = (
            "Opportunity brief parsing failed: "
            f"missing required field '{label}'."
        )
        raise ValueError(msg)

    if not brief.problem_statements:
        msg = (
            "Opportunity brief parsing failed: "
            "missing required field 'Problem statements'."
        )
        raise ValueError(msg)
