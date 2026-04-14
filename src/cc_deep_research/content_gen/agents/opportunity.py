"""Opportunity planning agent."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

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

# Parse path tracking for stage traces
_PARSE_MODE_NONE = "none"
_PARSE_MODE_JSON = "json"
_PARSE_MODE_LEGACY = "legacy"


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
        brief, parse_mode = _parse_opportunity_brief(text, theme)
        # Expose parse mode for stage trace metadata
        brief._parse_mode = parse_mode  # type: ignore[attr-defined]
        return brief


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


def _parse_from_json(text: str, fallback_theme: str) -> tuple[OpportunityBrief, str] | tuple[None, None]:
    """Attempt to parse OpportunityBrief from JSON-formatted LLM output.

    Returns (brief, _PARSE_MODE_JSON) on success.
    Returns (None, None) if JSON cannot be extracted or parsed.
    """
    # Strip code fences if present
    stripped = text.strip()
    if stripped.startswith("```"):
        # Handle both ```json and ``` (plain)
        fence_end = stripped.find("\n")
        if fence_end != -1:
            stripped = stripped[fence_end + 1:]
        # Remove trailing ```
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()

    # Try to find JSON object (may be wrapped in other text)
    json_start = stripped.find("{")
    json_end = stripped.rfind("}")
    if json_start == -1 or json_end == -1:
        return None, None

    json_str = stripped[json_start : json_end + 1]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None, None

    if not isinstance(data, dict):
        return None, None

    # Map JSON fields to OpportunityBrief, coercing list fields to lists
    def _coerce_list(val: Any) -> list[str]:
        if val is None:
            return []
        if isinstance(val, list):
            return [str(v) for v in val]
        return [str(val)]

    raw = {
        "theme": str(data.get("theme", "") or "").strip() or fallback_theme,
        "goal": str(data.get("goal", "") or "").strip(),
        "primary_audience_segment": str(data.get("primary_audience_segment", "") or "").strip(),
        "secondary_audience_segments": _coerce_list(data.get("secondary_audience_segments")),
        "problem_statements": _coerce_list(data.get("problem_statements")),
        "content_objective": str(data.get("content_objective", "") or "").strip(),
        "proof_requirements": _coerce_list(data.get("proof_requirements")),
        "platform_constraints": _coerce_list(data.get("platform_constraints")),
        "risk_constraints": _coerce_list(data.get("risk_constraints")),
        "freshness_rationale": str(data.get("freshness_rationale", "") or "").strip(),
        "sub_angles": _coerce_list(data.get("sub_angles")),
        "research_hypotheses": _coerce_list(data.get("research_hypotheses")),
        "success_criteria": _coerce_list(data.get("success_criteria")),
        "expert_take": str(data.get("expert_take", "") or "").strip(),
        "non_obvious_claims_to_test": _coerce_list(data.get("non_obvious_claims_to_test")),
        "genericity_risks": _coerce_list(data.get("genericity_risks")),
    }

    brief = OpportunityBrief.model_validate(raw)
    return brief, _PARSE_MODE_JSON


def _parse_opportunity_brief(text: str, fallback_theme: str) -> tuple[OpportunityBrief, str]:
    """Parse an opportunity brief from LLM output.

    Tries JSON first, falls back to legacy text format. Returns the parsed
    brief and the parse mode used ('json', 'legacy', or 'none').
    """
    # Try structured JSON first
    brief, parse_mode = _parse_from_json(text, fallback_theme)
    if brief is not None:
        _validate_opportunity_brief(brief)
        return brief, parse_mode

    # Fall back to legacy header/text parsing
    brief = _parse_opportunity_brief_legacy(text, fallback_theme)
    _validate_opportunity_brief(brief)
    return brief, _PARSE_MODE_LEGACY


def _parse_opportunity_brief_legacy(text: str, fallback_theme: str) -> OpportunityBrief:
    """Parse OpportunityBrief from legacy header-and-dash text format."""
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

    return OpportunityBrief(
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


class BriefQualityWarning:
    """A quality warning for an opportunity brief."""

    def __init__(self, category: str, message: str) -> None:
        self.category = category
        self.message = message

    def __repr__(self) -> str:
        return f"[{self.category}] {self.message}"


def _check_audience_specificity(brief: OpportunityBrief) -> list[BriefQualityWarning]:
    """Check if the primary audience segment is too generic."""
    warnings: list[BriefQualityWarning] = []
    segment = (brief.primary_audience_segment or "").lower()
    generic_terms = ["everyone", "anybody", "any audience", "marketers", "businesses", "people", "users", "customers", "general audience"]
    if any(term in segment for term in generic_terms):
        warnings.append(
            BriefQualityWarning(
                "audience_generic",
                f"Primary audience segment is too generic: '{brief.primary_audience_segment}'. "
                "Specify a concrete segment (e.g., 'seed-stage SaaS founders with >$50k ARR').",
            )
        )
    return warnings


def _check_problem_observability(brief: OpportunityBrief) -> list[BriefQualityWarning]:
    """Check if problem statements describe observable, real problems."""
    warnings: list[BriefQualityWarning] = []
    vague_indicators = [
        ("misses the point", "problem may not be actionable"),
        ("not engaging", "problem is subjective, not observable"),
        ("lacks clarity", "problem is vague, not specific"),
        ("not resonating", "problem is subjective"),
        ("feels off", "problem is vague"),
    ]
    generic_problems = ["not good enough", "could be better", "needs improvement", "is broken", "is wrong"]
    for ps in (brief.problem_statements or []):
        ps_lower = ps.lower()
        # Check for generic/vague problems
        if any(gp in ps_lower for gp in generic_problems):
            warnings.append(
                BriefQualityWarning(
                    "problem_vague",
                    f"Problem statement is too generic: '{ps}'. "
                    "Describe a concrete, observable symptom.",
                )
            )
        # Check for vague indicators
        for indicator, reason in vague_indicators:
            if indicator in ps_lower:
                warnings.append(
                    BriefQualityWarning(
                        "problem_vague",
                        f"Problem statement contains vague language ('{indicator}'): '{ps}'. {reason}.",
                    )
                )
    return warnings


def _check_proof_requirements(brief: OpportunityBrief) -> list[BriefQualityWarning]:
    """Check if proof requirements are specific and actionable."""
    warnings: list[BriefQualityWarning] = []
    vague_terms = ["some evidence", "any data", "proof", "evidence", "citation", "source"]
    generic_terms = ["more research", "further study", "additional data", "general data"]
    for pr in (brief.proof_requirements or []):
        pr_lower = pr.lower()
        if any(term in pr_lower for term in vague_terms):
            # Check if it's also generic
            if any(term in pr_lower for term in generic_terms):
                warnings.append(
                    BriefQualityWarning(
                        "proof_vague",
                        f"Proof requirement is too generic: '{pr}'. "
                        "Specify what specific data, metric, or source is needed.",
                    )
                )
    return warnings


def _check_duplicate_sub_angles(brief: OpportunityBrief) -> list[BriefQualityWarning]:
    """Detect sub-angles that are restatements of each other."""
    warnings: list[BriefQualityWarning] = []
    sub_angles_lower = [sa.lower().strip() for sa in (brief.sub_angles or [])]
    # Check for exact duplicates
    seen: set[str] = set()
    for sa in sub_angles_lower:
        if sa in seen:
            warnings.append(
                BriefQualityWarning(
                    "sub_angle_duplicate",
                    f"Sub-angle appears more than once: '{sa}'. "
                    "Each sub-angle should be a distinct editorial direction.",
                )
            )
        seen.add(sa)
    # Check for near-duplicates (one is substring of another)
    for i, sa1 in enumerate(sub_angles_lower):
        for sa2 in sub_angles_lower[i + 1 :]:
            if len(sa1) > 5 and len(sa2) > 5:
                # If one contains the other as a significant part
                if sa1 in sa2 or sa2 in sa1:
                    warnings.append(
                        BriefQualityWarning(
                            "sub_angle_near_duplicate",
                            f"Sub-angles may be restatements: '{brief.sub_angles[sub_angles_lower.index(sa1)]}' "
                            f"and '{brief.sub_angles[sub_angles_lower.index(sa2)]}'. "
                            "Ensure each is a distinct direction.",
                        )
                    )
    return warnings


def _check_genericity_risks(brief: OpportunityBrief) -> list[BriefQualityWarning]:
    """Detect risks that the brief is too generic or clichéd."""
    warnings: list[BriefQualityWarning] = []
    generic_claims = ["everyone knows", "commonly known", "industry standard", "best practice", "it depends"]
    for claim in (brief.genericity_risks or []):
        claim_lower = claim.lower()
        if any(gc in claim_lower for gc in generic_claims):
            warnings.append(
                BriefQualityWarning(
                    "genericity_risk",
                    f"Genericity risk may be too generic to be useful: '{claim}'.",
                )
            )
    return warnings


def validate_opportunity_brief_quality(brief: OpportunityBrief) -> tuple[list[BriefQualityWarning], bool]:
    """Validate the editorial quality of an opportunity brief.

    Returns (warnings, is_acceptable) where is_acceptable is True if the brief
    has no blocking quality issues. Warnings are categorized and human-readable.

    A brief is considered acceptable if:
    - All required scalar fields are non-empty
    - At least one problem statement is specific enough
    - No more than one audience_generic warning (can proceed with caution)
    - No more than one problem_vague warning
    """
    all_warnings: list[BriefQualityWarning] = []
    all_warnings.extend(_check_audience_specificity(brief))
    all_warnings.extend(_check_problem_observability(brief))
    all_warnings.extend(_check_proof_requirements(brief))
    all_warnings.extend(_check_duplicate_sub_angles(brief))
    all_warnings.extend(_check_genericity_risks(brief))

    # Determine acceptability based on warning counts
    audience_generic_count = sum(1 for w in all_warnings if w.category == "audience_generic")
    problem_vague_count = sum(1 for w in all_warnings if w.category == "problem_vague")
    proof_vague_count = sum(1 for w in all_warnings if w.category == "proof_vague")
    duplicate_count = sum(1 for w in all_warnings if "duplicate" in w.category)

    # Blocking conditions: too many critical warnings
    is_acceptable = not (
        audience_generic_count > 1
        or problem_vague_count > 2
        or proof_vague_count > 1
        or duplicate_count > 0
    )

    return all_warnings, is_acceptable


def format_quality_summary(warnings: list[BriefQualityWarning]) -> str:
    """Format quality warnings into a human-readable summary for operators."""
    if not warnings:
        return "Brief quality: acceptable."

    lines = [f"Brief quality: {len(warnings)} warning(s) found."]
    by_category: dict[str, list[BriefQualityWarning]] = {}
    for w in warnings:
        by_category.setdefault(w.category, []).append(w)

    for category, ws in by_category.items():
        lines.append(f"  [{category}] ({len(ws)}):")
        for w in ws:
            lines.append(f"    - {w.message}")

    return "\n".join(lines)
