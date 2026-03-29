"""Backlog builder and idea scorer agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models import (
    BacklogItem,
    BacklogOutput,
    IdeaScores,
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
        response = await self._router.execute(
            AGENT_ID,
            user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return response.content

    # ------------------------------------------------------------------
    # Build backlog
    # ------------------------------------------------------------------

    async def build_backlog(
        self,
        theme: str,
        strategy: StrategyMemory,
        *,
        count: int = 20,
    ) -> BacklogOutput:
        system = prompts.BUILD_BACKLOG_SYSTEM
        user = prompts.build_backlog_user(theme, strategy, count=count)
        text = await self._call_llm(system, user, temperature=0.7)

        items = _parse_backlog_items(text)
        rejected_count = _extract_int_field(text, "Rejected ideas")
        rejection_reasons = _extract_list_section(text, "Rejection reasons")

        return BacklogOutput(
            items=items,
            rejected_count=rejected_count,
            rejection_reasons=rejection_reasons,
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
            return ScoringOutput()

        system = prompts.SCORE_IDEAS_SYSTEM
        user = prompts.score_ideas_user(items, strategy, threshold=threshold)
        text = await self._call_llm(system, user, temperature=0.3)

        scores = _parse_scores(text, items)
        produce_now = [s.idea_id for s in scores if s.recommendation == "produce_now"]
        hold = [s.idea_id for s in scores if s.recommendation == "hold"]
        killed = [s.idea_id for s in scores if s.recommendation == "kill"]

        return ScoringOutput(
            scores=scores,
            produce_now=produce_now,
            hold=hold,
            killed=killed,
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_BACKLOG_FIELDS = [
    "category",
    "idea",
    "audience",
    "problem",
    "source",
    "why_now",
    "potential_hook",
    "content_type",
    "evidence",
    "risk_level",
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
        if data.get("idea"):
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
                dim_scores[field] = 0
        total_str = _extract_block_field(block_text, "total_score")
        try:
            total = int(total_str)
        except (ValueError, TypeError):
            total = sum(dim_scores.values())
        rec = _extract_block_field(block_text, "recommendation").lower()
        if rec not in ("produce_now", "hold", "kill"):
            rec = "hold"
        reason = _extract_block_field(block_text, "reason")
        scores.append(
            IdeaScores(
                idea_id=idea_id,
                total_score=total,
                recommendation=rec,
                reason=reason,
                **dim_scores,  # type: ignore[arg-type]
            )
        )
    return scores
