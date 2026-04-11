"""Production brief agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import ProductionBrief, VisualPlanOutput
from cc_deep_research.content_gen.prompts import production as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_production"


def _maybe_set_degraded(brief: ProductionBrief, text: str) -> None:
    """Set degraded state on ProductionBrief if output is partial or empty."""
    if not text:
        brief.is_degraded = True
        brief.degradation_reason = "blank LLM response after retry"
        return

    list_fields = [
        brief.props,
        brief.assets_to_prepare,
        brief.audio_checks,
        brief.battery_checks,
        brief.storage_checks,
        brief.pickup_lines_to_capture,
    ]
    scalar_fields = [brief.location, brief.setup, brief.wardrobe, brief.backup_plan]

    non_empty_lists = [f for f in list_fields if f]
    non_empty_scalars = [f for f in scalar_fields if f]

    if not non_empty_lists and not non_empty_scalars:
        brief.is_degraded = True
        brief.degradation_reason = "parser produced zero usable records"
        return

    empty_lists = [f for f in list_fields if not f]
    if empty_lists:
        brief.is_degraded = True
        list_field_names = ["props", "assets_to_prepare", "audio_checks", "battery_checks",
                           "storage_checks", "pickup_lines_to_capture"]
        missing = [list_field_names[i] for i, f in enumerate(list_fields) if not f]
        brief.degradation_reason = f"parser produced partial records; missing: {', '.join(missing)}"


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
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="production brief workflow",
            cli_command="content-gen production",
            logger=logger,
            allow_blank=True,
        )

    async def brief(
        self,
        visual_plan: VisualPlanOutput,
    ) -> ProductionBrief:
        system = prompts.PRODUCTION_SYSTEM
        user = prompts.production_user(visual_plan)
        text = await self._call_llm(system, user, temperature=0.3)

        brief = _parse_production_brief(text, visual_plan.idea_id)

        # Detect and record degraded state
        _maybe_set_degraded(brief, text)

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
