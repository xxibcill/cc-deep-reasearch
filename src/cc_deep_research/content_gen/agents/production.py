"""Production brief agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models import ProductionBrief, VisualPlanOutput
from cc_deep_research.content_gen.prompts import production as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_production"


class ProductionAgent:
    """Generate an idiot-proof production brief from the visual plan."""

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
        temperature: float = 0.3,
    ) -> str:
        response = await self._router.execute(
            AGENT_ID,
            user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return response.content

    async def brief(
        self,
        visual_plan: VisualPlanOutput,
    ) -> ProductionBrief:
        system = prompts.PRODUCTION_SYSTEM
        user = prompts.production_user(visual_plan)
        text = await self._call_llm(system, user, temperature=0.3)

        return _parse_production_brief(text, visual_plan.idea_id)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_list(text: str, header: str) -> list[str]:
    items: list[str] = []
    in_section = False
    for line in text.split("\n"):
        stripped = line.strip()
        if header.lower().replace("_", " ") in stripped.lower().replace("_", " "):
            in_section = True
            continue
        if in_section:
            if stripped.startswith("- ") or stripped.startswith("* "):
                items.append(stripped[2:].strip())
            elif (
                stripped
                and not stripped.startswith("-")
                and not stripped.startswith("*")
                and re.match(r"[a-z_]+:", stripped)
            ):
                break
    return items


_LIST_FIELDS = [
    "props",
    "assets_to_prepare",
    "audio_checks",
    "battery_checks",
    "storage_checks",
    "pickup_lines_to_capture",
]


def _parse_production_brief(text: str, idea_id: str) -> ProductionBrief:
    data: dict = {"idea_id": idea_id}
    for field in ("location", "setup", "wardrobe", "backup_plan"):
        data[field] = _extract_field(text, field)
    for field in _LIST_FIELDS:
        data[field] = _extract_list(text, field)
    return ProductionBrief(**data)
