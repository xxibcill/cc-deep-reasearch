"""Backlog builder and idea scorer agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import (
    BacklogItem,
    BacklogOutput,
    IdeaScores,
    OpportunityBrief,
    ScoringOutput,
    StrategyMemory,
)
from cc_deep_research.content_gen.prompts import backlog as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_backlog"


class BacklogAgent:
    """Build and score content idea backlog."""

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
            workflow_name="content backlog workflow",
            cli_command="content-gen backlog",
            logger=logger,
            allow_blank=True,
        )

    # ------------------------------------------------------------------
    # Build backlog
    # ------------------------------------------------------------------

    async def build_backlog(
        self,
        theme: str,
        strategy: StrategyMemory,
        *,
        count: int = 20,
        opportunity_brief: OpportunityBrief | None = None,
    ) -> BacklogOutput:
        system = prompts.BUILD_BACKLOG_SYSTEM
        user = prompts.build_backlog_user(theme, strategy, count=count, opportunity_brief=opportunity_brief)
        text = await self._call_llm(system, user, temperature=0.7)

        items = _parse_backlog_items(text)
        rejected_count = _extract_int_field(text, "Rejected ideas")
        rejection_reasons = _extract_list_section(text, "Rejection reasons")

        is_degraded = False
        degradation_reason = ""
        if not items:
            is_degraded = True
            degradation_reason = "zero valid ideas parsed from LLM response"

        brief_id = opportunity_brief.brief_id if opportunity_brief else ""
        if brief_id:
            for item in items:
                item.opportunity_brief_id = brief_id

        return BacklogOutput(
            items=items,
            rejected_count=rejected_count,
            rejection_reasons=rejection_reasons,
            is_degraded=is_degraded,
            degradation_reason=degradation_reason,
        )

    # ------------------------------------------------------------------
    # Score ideas
    # ------------------------------------------------------------------

    async def score_ideas(
        self,
        items: list[BacklogItem],
        strategy: StrategyMemory,
        *,
        threshold: int = 25,
    ) -> ScoringOutput:
        if not items:
            logger.warning("Scoring called with empty items list")
            return ScoringOutput()

        system = prompts.SCORE_IDEAS_SYSTEM
        user = prompts.score_ideas_user(items, strategy, threshold=threshold)
        text = await self._call_llm(system, user, temperature=0.3)

        scores = _parse_scores(text, items)

        if not scores:
            logger.warning("Scoring parsing produced zero valid scores from LLM response")

        valid_scores = _validate_scores(scores)
        if len(valid_scores) != len(scores):
            invalid_count = len(scores) - len(valid_scores)
            logger.warning(f"Scoring output contained {invalid_count} invalid recommendations, defaulting to 'hold'")

        produce_now = [s.idea_id for s in valid_scores if s.recommendation == "produce_now"]
        shortlist, selected_idea_id, selection_reasoning, runner_up_idea_ids = _derive_selection(
            text,
            valid_scores,
            items,
        )
        hold = [s.idea_id for s in valid_scores if s.recommendation == "hold"]
        killed = [s.idea_id for s in valid_scores if s.recommendation == "kill"]

        is_degraded = False
        degradation_reason = ""
        if not valid_scores:
            is_degraded = True
            degradation_reason = "zero valid scores parsed from LLM response"

        return ScoringOutput(
            scores=valid_scores,
            produce_now=produce_now,
            shortlist=shortlist,
            selected_idea_id=selected_idea_id,
            selection_reasoning=selection_reasoning,
            runner_up_idea_ids=runner_up_idea_ids,
            hold=hold,
            killed=killed,
            is_degraded=is_degraded,
            degradation_reason=degradation_reason,
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_BACKLOG_FIELDS = [
    "category",
    "title",
    "one_line_summary",
    "raw_idea",
    "constraints",
    "source_theme",
    "audience",
    "persona_detail",
    "problem",
    "emotional_driver",
    "urgency_level",
    "why_now",
    "hook",
    "content_type",
    "format_duration",
    "key_message",
    "call_to_action",
    "evidence",
    "proof_gap_note",
    "expertise_reason",
    "genericity_risk",
    "risk_level",
    "source",
    # Legacy field aliases (map to canonical fields in BacklogItem model)
    "idea",
    "potential_hook",
]


def _parse_backlog_items(text: str) -> list[BacklogItem]:
    items: list[BacklogItem] = []
    blocks = re.split(r"---+", text)
    for block in blocks:
        block_text = block.strip()
        if not block_text:
            continue
        data: dict = {}
        for field in _BACKLOG_FIELDS:
            val = _extract_block_field(block_text, field)
            if val:
                data[field] = val
        if data.get("title"):
            items.append(BacklogItem(**data))
    return items


def _extract_block_field(text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_int_field(text: str, field_name: str) -> int:
    pattern = rf"{re.escape(field_name)}:\s*(\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


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


_SCORE_FIELDS = [
    "relevance",
    "novelty",
    "authority_fit",
    "production_ease",
    "evidence_strength",
    "hook_strength",
    "repurposing",
    "opportunity_fit",
]


def _parse_scores(text: str, _items: list[BacklogItem]) -> list[IdeaScores]:
    scores: list[IdeaScores] = []
    blocks = re.split(r"---+", text)
    for block in blocks:
        block_text = block.strip()
        if not block_text:
            continue
        idea_id = _extract_block_field(block_text, "idea_id")
        if not idea_id:
            continue
        dim_scores: dict[str, int] = {}
        for field in _SCORE_FIELDS:
            val = _extract_block_field(block_text, field)
            try:
                dim_scores[field] = max(1, min(5, int(val)))
            except (ValueError, TypeError):
                dim_scores[field] = 1
        total_str = _extract_block_field(block_text, "total_score")
        try:
            total = int(total_str)
        except (ValueError, TypeError):
            total = sum(dim_scores.values())
        rec = _extract_block_field(block_text, "recommendation").lower()
        if rec not in ("produce_now", "hold", "kill"):
            rec = "hold"
        reason = _extract_block_field(block_text, "reason")
        opportunity_fit_reason = _extract_block_field(block_text, "opportunity_fit_reason")
        scores.append(
            IdeaScores(
                idea_id=idea_id,
                total_score=total,
                recommendation=rec,
                reason=reason,
                opportunity_fit_reason=opportunity_fit_reason,
                **dim_scores,  # type: ignore[arg-type]
            )
        )
    return scores


def _validate_scores(scores: list[IdeaScores]) -> list[IdeaScores]:
    valid_recommendations = {"produce_now", "hold", "kill"}
    validated: list[IdeaScores] = []
    for score in scores:
        if score.recommendation not in valid_recommendations:
            score.recommendation = "hold"
        validated.append(score)
    return validated


def _derive_selection(
    text: str,
    scores: list[IdeaScores],
    items: list[BacklogItem],
) -> tuple[list[str], str, str, list[str]]:
    produce_now_scores = [score for score in scores if score.recommendation == "produce_now"]
    if not produce_now_scores:
        return [], "", "", []

    valid_ids = {score.idea_id for score in produce_now_scores}
    ranked_scores = _rank_scores(produce_now_scores, items)
    fallback_shortlist = [score.idea_id for score in ranked_scores]
    parsed_shortlist = [
        idea_id for idea_id in _extract_shortlist(text, valid_ids) if idea_id in valid_ids
    ]
    shortlist = _merge_preserving_order(parsed_shortlist, fallback_shortlist)

    selected_idea_id = _normalize_idea_id(_extract_block_field(text, "selected_idea_id"), valid_ids)
    if not selected_idea_id or selected_idea_id not in shortlist:
        selected_idea_id = shortlist[0]

    selection_reasoning = _extract_block_field(text, "selection_reasoning").strip()
    if not selection_reasoning:
        selected_score = next((score for score in ranked_scores if score.idea_id == selected_idea_id), None)
        selection_reasoning = selected_score.reason if selected_score else ""

    runner_up_idea_ids = [idea_id for idea_id in shortlist if idea_id != selected_idea_id]
    return shortlist, selected_idea_id, selection_reasoning, runner_up_idea_ids


def _extract_shortlist(text: str, valid_ids: set[str]) -> list[str]:
    raw_entries = _extract_list_section(text, "shortlist")
    shortlist: list[str] = []
    for entry in raw_entries:
        idea_id = _normalize_idea_id(entry, valid_ids)
        if idea_id and idea_id not in shortlist:
            shortlist.append(idea_id)
    return shortlist


def _normalize_idea_id(raw_value: str, valid_ids: set[str]) -> str:
    cleaned = re.sub(r"^\d+[\.\)]\s*", "", raw_value).strip()
    candidate = cleaned.split(":", 1)[0].strip()
    candidate = candidate.split(" ", 1)[0].strip()
    if candidate in valid_ids:
        return candidate
    for idea_id in valid_ids:
        if re.search(rf"\b{re.escape(idea_id)}\b", cleaned):
            return idea_id
    return ""


def _rank_scores(scores: list[IdeaScores], items: list[BacklogItem]) -> list[IdeaScores]:
    item_order = {item.idea_id: index for index, item in enumerate(items)}
    return sorted(
        scores,
        key=lambda score: (-score.total_score, item_order.get(score.idea_id, len(item_order))),
    )


def _merge_preserving_order(primary: list[str], fallback: list[str]) -> list[str]:
    merged: list[str] = []
    for idea_id in [*primary, *fallback]:
        if idea_id and idea_id not in merged:
            merged.append(idea_id)
    return merged
