"""Angle generator agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
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
_ANGLE_REQUIRED_FIELDS = (
    "target_audience",
    "viewer_problem",
    "core_promise",
    "primary_takeaway",
)

_ANGLE_FIELDS = [
    "angle_id",
    "target_audience",
    "viewer_problem",
    "core_promise",
    "primary_takeaway",
    "lens",
    "format",
    "tone",
    "cta",
    "why_this_version_should_exist",
    "differentiation_summary",
    "market_framing_challenged",
    "genericity_risks",
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
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="angle generation workflow",
            cli_command="content-gen pipeline",
            logger=logger,
        )

    async def generate(
        self,
        item: BacklogItem,
        strategy: StrategyMemory,
    ) -> AngleOutput:
        system = prompts.ANGLE_SYSTEM
        user = prompts.angle_user(item, strategy)
        text = await self._call_llm(system, user, temperature=0.6)

        options = _parse_angle_options(text)
        if not options:
            msg = (
                "Angle parsing failed: missing at least one complete angle option "
                "with audience, problem, promise, and takeaway."
            )
            raise ValueError(msg)
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


def _extract_list_field(text: str, field_name: str) -> list[str]:
    """Extract a '-' list field from a block.

    Finds the field_name: line, then collects list items from subsequent lines
    that start with '- ' or '* ' until a non-list line (field header or
    empty continuation) is encountered.
    """
    # Find the line that contains "field_name:"
    lines = text.split("\n")
    field_line_idx = -1
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(field_name)}:\s*$", line.strip(), re.IGNORECASE):
            field_line_idx = i
            break

    if field_line_idx == -1:
        return []

    items: list[str] = []
    for line in lines[field_line_idx + 1:]:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            items.append(stripped[2:].strip())
        elif stripped == "":
            # Empty line — continue collecting if we already have items
            continue
        else:
            # Non-list, non-empty line — either a new field header or unexpected content
            # Stop if we haven't started collecting yet (could be a continuation
            # from previous field that doesn't start with dash), but if we have
            # items, this non-list line ends the list
            break

    return items


def _parse_angle_options(text: str) -> list[AngleOption]:
    options: list[AngleOption] = []
    blocks = re.split(r"---+", text)
    for block in blocks:
        block_text = block.strip()
        if not block_text:
            continue
        data: dict = {}
        for field in _ANGLE_FIELDS:
            if field == "genericity_risks":
                val = _extract_list_field(block_text, field)
            else:
                val = _extract_field(block_text, field)
            if val:
                data[field] = val
        if _is_complete_angle_option(data):
            options.append(AngleOption(**data))
    return options


def _is_complete_angle_option(data: dict[str, str]) -> bool:
    return all(data.get(field) for field in _ANGLE_REQUIRED_FIELDS)
