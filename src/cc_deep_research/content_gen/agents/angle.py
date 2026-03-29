"""Angle generator agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models import (
    AngleOption,
    AngleOutput,
    BacklogItem,
    StrategyMemory,
)
from cc_deep_research.content_gen.prompts import angle as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_angle"

_ANGLE_FIELDS = [
    "target_audience",
    "viewer_problem",
    "core_promise",
    "primary_takeaway",
    "lens",
    "format",
    "tone",
    "cta",
    "why_this_version_should_exist",
]


class AngleAgent:
    """Generate 3-5 editorial angles for a selected content idea."""

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

    async def generate(
        self,
        item: BacklogItem,
        strategy: StrategyMemory,
    ) -> AngleOutput:
        system = prompts.ANGLE_SYSTEM
        user = prompts.angle_user(item, strategy)
        text = await self._call_llm(system, user, temperature=0.6)

        options = _parse_angle_options(text)
        best_id = _extract_field(text, "Best angle_id")
        reasoning = _extract_field(text, "Selection reasoning")

        return AngleOutput(
            idea_id=item.idea_id,
            angle_options=options,
            selected_angle_id=best_id,
            selection_reasoning=reasoning,
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _parse_angle_options(text: str) -> list[AngleOption]:
    options: list[AngleOption] = []
    blocks = re.split(r"---+", text)
    for block in blocks:
        block_text = block.strip()
        if not block_text:
            continue
        data: dict = {}
        for field in _ANGLE_FIELDS:
            val = _extract_field(block_text, field)
            if val:
                data[field] = val
        # Only add if we got at least a core_promise or target_audience
        if data.get("core_promise") or data.get("target_audience"):
            options.append(AngleOption(**data))
    return options
