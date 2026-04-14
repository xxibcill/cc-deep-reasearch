"""Execution brief generation for backlog items.

Produces a compact AI brief that helps a superuser move a strong backlog item
into production faster.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import BacklogItem
from cc_deep_research.content_gen.prompts import execution_brief as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_execution_brief"


class ExecutionBrief(BaseModel):
    """A production-readiness brief for a backlog item."""

    idea_id: str
    # Audience and framing
    audience: str
    problem_statement: str
    hook_direction: str
    # Evidence requirements
    evidence_requirements: list[str] = Field(default_factory=list)
    proof_gaps: list[str] = Field(default_factory=list)
    # Research questions
    research_questions: list[str] = Field(default_factory=list)
    # Production risks
    risks_before_production: list[str] = Field(default_factory=list)
    # Readiness summary
    is_ready_for_production: bool = False
    readiness_summary: str = ""


class ExecutionBriefResponse(BaseModel):
    """Response from execution brief generation."""

    brief: ExecutionBrief
    source_item_summary: str  # Truncated idea for display


class ExecutionBriefAgent:
    """Generate production-readiness briefs for backlog items."""

    def __init__(self, config: Config | None = None) -> None:
        from cc_deep_research.llm.registry import LLMRouteRegistry

        if config is None:
            from cc_deep_research.config import load_config

            config = load_config()

        self._config = config
        registry = LLMRouteRegistry(config.llm)
        self._router = LLMRouter(registry)

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
    ) -> str:
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="execution brief",
            cli_command="content-gen execution-brief",
            logger=logger,
            allow_blank=False,
        )

    async def generate_brief(
        self,
        item: BacklogItem,
        *,
        strategy_context: dict[str, Any] | None = None,
    ) -> ExecutionBriefResponse:
        """Generate a production-readiness brief for a backlog item.

        Args:
            item: The backlog item to generate a brief for
            strategy_context: Optional strategy memory context

        Returns:
            ExecutionBriefResponse with the brief and source summary
        """
        system = prompts.EXECUTION_BRIEF_SYSTEM
        user = prompts.build_execution_brief_user(item, strategy=strategy_context)

        try:
            text = await self._call_llm(system, user, temperature=0.3)
            parsed = _parse_brief_response(text, item.idea_id)

            if parsed:
                return ExecutionBriefResponse(
                    brief=ExecutionBrief(**parsed),
                    source_item_summary=item.idea[:80],
                )
        except Exception as exc:
            logger.warning("Execution brief LLM call failed for %s: %s", item.idea_id, exc)

        # Fallback to heuristic brief
        fallback = _build_heuristic_brief(item)
        return ExecutionBriefResponse(
            brief=fallback,
            source_item_summary=item.idea[:80],
        )


async def generate_execution_brief(
    item: BacklogItem,
    config: Config | None = None,
    strategy_context: dict[str, Any] | None = None,
) -> ExecutionBriefResponse:
    """Convenience function for generating an execution brief."""
    agent = ExecutionBriefAgent(config)
    return await agent.generate_brief(item, strategy_context=strategy_context)


def _parse_brief_response(text: str, idea_id: str) -> dict[str, Any] | None:
    """Parse LLM output into an execution brief dict."""
    import json
    import re

    text = text.strip()

    # Try JSON directly
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "hook_direction" in parsed:
            return _sanitize_brief(parsed, idea_id)
    except json.JSONDecodeError:
        pass

    # Try JSON inside code fences
    fence_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
    for match in fence_pattern.finditer(text):
        candidate = match.group(1).strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "hook_direction" in parsed:
                return _sanitize_brief(parsed, idea_id)
        except json.JSONDecodeError:
            continue

    return None


def _sanitize_brief(parsed: dict, idea_id: str) -> dict[str, Any]:
    """Clean and validate LLM brief output."""
    def clean_str(s: Any, max_len: int = 500) -> str:
        return str(s)[:max_len] if s else ""

    def clean_list(lst: Any, max_items: int = 10, max_len: int = 300) -> list[str]:
        if not isinstance(lst, list):
            return []
        return [clean_str(x, max_len) for x in lst[:max_items] if x]

    return {
        "idea_id": idea_id,
        "audience": clean_str(parsed.get("audience", ""), 300),
        "problem_statement": clean_str(parsed.get("problem_statement", ""), 400),
        "hook_direction": clean_str(parsed.get("hook_direction", ""), 400),
        "evidence_requirements": clean_list(parsed.get("evidence_requirements", [])),
        "proof_gaps": clean_list(parsed.get("proof_gaps", [])),
        "research_questions": clean_list(parsed.get("research_questions", [])),
        "risks_before_production": clean_list(parsed.get("risks_before_production", [])),
        "is_ready_for_production": bool(parsed.get("is_ready_for_production", False)),
        "readiness_summary": clean_str(parsed.get("readiness_summary", ""), 300),
    }


def _build_heuristic_brief(item: BacklogItem) -> ExecutionBrief:
    """Build a heuristic brief when LLM fails."""
    # Assess readiness
    strong_fields = []
    if item.audience and len(item.audience) >= 20:
        strong_fields.append("audience")
    if item.problem and len(item.problem) >= 30:
        strong_fields.append("problem")
    if item.why_now and len(item.why_now) >= 20:
        strong_fields.append("why_now")
    if item.potential_hook and len(item.potential_hook) >= 20:
        strong_fields.append("hook")
    if item.evidence and len(item.evidence) >= 50:
        strong_fields.append("evidence")

    is_ready = len(strong_fields) >= 4

    proof_gaps = []
    if not item.evidence or len(item.evidence) < 50:
        proof_gaps.append("Evidence is weak or missing")
    if not item.proof_gap_note:
        proof_gaps.append("No proof gap analysis recorded")

    research_questions = []
    if item.audience:
        research_questions.append(f"What does '{item.audience}' actually want to hear?")
    if item.problem:
        research_questions.append(f"What evidence supports the '{item.problem}' framing?")

    risks = []
    if item.risk_level == "high":
        risks.append("High risk level — verify claims before production")
    if item.genericity_risk:
        risks.append(f"Genericity risk: {item.genericity_risk[:100]}")
    if not item.potential_hook or len(item.potential_hook) < 20:
        risks.append("Hook is missing or underdeveloped")

    return ExecutionBrief(
        idea_id=item.idea_id,
        audience=item.audience or "Audience not clearly defined",
        problem_statement=item.problem or "Problem statement needs development",
        hook_direction=item.potential_hook or "Hook direction not specified",
        evidence_requirements=["Specific proof points", "Supporting data or examples"] if not item.evidence else [],
        proof_gaps=proof_gaps,
        research_questions=research_questions,
        risks_before_production=risks,
        is_ready_for_production=is_ready,
        readiness_summary=f"{len(strong_fields)}/6 editorial fields are strong" if strong_fields else "Item needs more editorial development before production",
    )

