"""Single-item next-action recommendation for backlog items.

Produces per-item AI guidance telling the superuser what should happen next
and why, grounded in existing scoring metadata and backlog fields.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import BacklogItem
from cc_deep_research.content_gen.prompts import next_action as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_next_action"


class NextActionRecommendation(BaseModel):
    """A single next-action recommendation for a backlog item."""

    action: str  # produce | reframe | gather_evidence | hold | archive
    rationale: str  # Why this action is recommended
    confidence: float = Field(ge=0.0, le=1.0)  # 0=low, 1=high
    blockers: list[str] = Field(default_factory=list)  # What's preventing action
    suggested_fields: dict[str, str] = Field(default_factory=dict)  # Field -> suggested value


class NextActionResponse(BaseModel):
    """Structured response for a single-item next-action query."""

    recommendation: NextActionRecommendation
    item_summary: str  # Brief description of the item for context


class NextActionBatchResponse(BaseModel):
    """Batch next-action response for multiple items."""

    recommendations: list[NextActionRecommendation]
    item_ids: list[str]
    warnings: list[str] = Field(default_factory=list)


def _derive_action_from_scores(item: BacklogItem) -> tuple[str, float]:
    """Derive a heuristic action from existing scoring metadata.

    This is a fast-path used when LLM analysis isn't needed or as a fallback.
    """
    rec = item.latest_recommendation
    score = item.latest_score

    if rec == "produce_now":
        return "produce", 0.85
    if rec == "kill":
        return "archive", 0.9
    if rec == "hold":
        return "hold", 0.7

    # No recommendation yet — infer from score and content completeness
    if score is not None and score >= 75:
        return "produce", 0.6
    if score is not None and score < 40:
        return "archive", 0.5

    return "gather_evidence", 0.5


def _assess_blockers(item: BacklogItem) -> list[str]:
    """Identify what's preventing a stronger recommendation."""
    blockers = []

    if not item.evidence or len(item.evidence) < 50:
        blockers.append("missing or weak evidence")
    if not item.why_now or len(item.why_now) < 30:
        blockers.append("missing why_now / timeliness")
    if not item.potential_hook or len(item.potential_hook) < 30:
        blockers.append("missing or weak hook")
    if not item.audience or len(item.audience) < 20:
        blockers.append("unclear audience")
    if item.genericity_risk and len(item.genericity_risk) > 20:
        blockers.append(f"genericity risk: {item.genericity_risk[:50]}")
    if item.proof_gap_note:
        blockers.append(f"proof gap: {item.proof_gap_note[:50]}")

    return blockers


def _suggest_field_changes(item: BacklogItem, action: str) -> dict[str, str]:
    """Suggest field changes based on the recommended action."""
    suggestions: dict[str, str] = {}

    if action == "produce":
        # Item is ready — suggest production start
        pass  # No field changes, just status change

    elif action == "reframe":
        if not item.problem or len(item.problem) < 30:
            suggestions["problem"] = "Reframe: sharpen the core problem being solved"
        if not item.potential_hook or len(item.potential_hook) < 30:
            suggestions["potential_hook"] = "Reframe: develop a more compelling hook"

    elif action == "gather_evidence":
        if not item.evidence or len(item.evidence) < 50:
            suggestions["evidence"] = "Add specific proof points, data, or examples"
        if not item.proof_gap_note:
            suggestions["proof_gap_note"] = "Note what evidence would close the gap"

    elif action == "archive":
        pass  # Archive is a status operation, no field enrichment

    return suggestions


class NextActionAgent:
    """Single-item next-action recommendation agent."""

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
        temperature: float = 0.2,
    ) -> str:
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="next action",
            cli_command="content-gen next-action",
            logger=logger,
            allow_blank=False,
        )

    async def recommend(
        self,
        item: BacklogItem,
        *,
        strategy_context: dict[str, Any] | None = None,
    ) -> NextActionResponse:
        """Generate a next-action recommendation for a single backlog item.

        Args:
            item: The backlog item to analyze
            strategy_context: Optional strategy memory context

        Returns:
            NextActionResponse with recommendation and rationale
        """
        # Fast heuristic first — use as fallback
        action, confidence = _derive_action_from_scores(item)
        blockers = _assess_blockers(item)
        suggested_fields = _suggest_field_changes(item, action)

        system = prompts.NEXT_ACTION_SYSTEM
        user = prompts.build_next_action_user(item, strategy=strategy_context)

        try:
            text = await self._call_llm(system, user, temperature=0.2)
            parsed = _parse_llm_response(text, item)

            if parsed:
                return NextActionResponse(
                    recommendation=NextActionRecommendation(**parsed),
                    item_summary=item.idea[:80],
                )
        except Exception as exc:
            logger.warning("Next-action LLM call failed for %s: %s", item.idea_id, exc)

        # Fallback to heuristic
        rationale = _build_heuristic_rationale(item, action, blockers)
        return NextActionResponse(
            recommendation=NextActionRecommendation(
                action=action,
                rationale=rationale,
                confidence=confidence,
                blockers=blockers,
                suggested_fields=suggested_fields,
            ),
            item_summary=item.idea[:80],
        )


async def get_next_action(
    item: BacklogItem,
    config: Config | None = None,
    strategy_context: dict[str, Any] | None = None,
) -> NextActionResponse:
    """Convenience function for a single-item next-action recommendation."""
    agent = NextActionAgent(config)
    return await agent.recommend(item, strategy_context=strategy_context)


def _parse_llm_response(text: str, item: BacklogItem) -> dict[str, Any] | None:
    """Parse LLM output into a recommendation dict."""
    import json
    import re

    text = text.strip()

    # Try JSON directly
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "action" in parsed:
            return _sanitize_recommendation(parsed, item)
    except json.JSONDecodeError:
        pass

    # Try JSON inside code fences
    fence_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
    for match in fence_pattern.finditer(text):
        candidate = match.group(1).strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "action" in parsed:
                return _sanitize_recommendation(parsed, item)
        except json.JSONDecodeError:
            continue

    return None


VALID_ACTIONS = {"produce", "reframe", "gather_evidence", "hold", "archive"}


def _sanitize_recommendation(parsed: dict, item: BacklogItem) -> dict[str, Any]:
    """Clean and validate LLM recommendation output."""
    action = parsed.get("action", "")
    if action not in VALID_ACTIONS:
        action = "hold"

    rationale = str(parsed.get("rationale", ""))[:500]

    confidence = parsed.get("confidence")
    if confidence is None:
        confidence = 0.5
    try:
        confidence = float(confidence)
        confidence = max(0.0, min(1.0, confidence))
    except (ValueError, TypeError):
        confidence = 0.5

    blockers = parsed.get("blockers", [])
    if not isinstance(blockers, list):
        blockers = []
    blockers = [str(b)[:100] for b in blockers[:5]]

    suggested_fields = parsed.get("suggested_fields", {})
    if not isinstance(suggested_fields, dict):
        suggested_fields = {}
    # Only allow valid backlog item fields
    valid_fields = {
        "idea", "category", "audience", "problem", "source", "why_now",
        "potential_hook", "content_type", "evidence", "risk_level",
        "genericity_risk", "proof_gap_note",
    }
    suggested_fields = {
        k: str(v)[:500]
        for k, v in suggested_fields.items()
        if k in valid_fields and v
    }

    return {
        "action": action,
        "rationale": rationale,
        "confidence": confidence,
        "blockers": blockers,
        "suggested_fields": suggested_fields,
    }


def _build_heuristic_rationale(item: BacklogItem, action: str, blockers: list[str]) -> str:
    """Build a rationale string from heuristic analysis."""
    score = item.latest_score
    rec = item.latest_recommendation

    parts = []
    if rec:
        parts.append(f"Based on last scoring: recommendation = '{rec}'")
    if score is not None:
        parts.append(f"score = {score}")

    if blockers:
        parts.append(f"Primary gaps: {', '.join(blockers[:3])}")

    if not parts:
        parts.append(f"Item is in '{item.status}' status with incomplete editorial fields")

    return "; ".join(parts)

