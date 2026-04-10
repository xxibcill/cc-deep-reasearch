"""Visual translation agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import (
    BeatVisual,
    ScriptStructure,
    ScriptVersion,
    VisualPlanOutput,
)
from cc_deep_research.content_gen.prompts import visual as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_visual"


class VisualAgent:
    """Translate a script into a full beat-by-beat visual plan."""

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
            workflow_name="visual translation workflow",
            cli_command="content-gen visual",
            logger=logger,
        )

    async def translate(
        self,
        script: ScriptVersion,
        structure: ScriptStructure,
        *,
        idea_id: str = "",
        angle_id: str = "",
    ) -> VisualPlanOutput:
        system = prompts.VISUAL_SYSTEM
        user = prompts.visual_user(script, structure)
        text = await self._call_llm(system, user, temperature=0.4)

        plan = _parse_beat_visuals(text)
        refresh = _extract_field(text, "visual_refresh_check")
        if not plan:
            msg = (
                "Visual plan parsing failed: missing at least one complete beat "
                "with 'beat' and 'visual'."
            )
            raise ValueError(msg)
        if not refresh:
            msg = "Visual plan parsing failed: missing required field 'visual_refresh_check'."
            raise ValueError(msg)

        return VisualPlanOutput(
            idea_id=idea_id,
            angle_id=angle_id,
            visual_plan=plan,
            visual_refresh_check=refresh,
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_VISUAL_FIELDS = [
    "beat",
    "spoken_line",
    "visual",
    "shot_type",
    "a_roll",
    "b_roll",
    "on_screen_text",
    "overlay_or_graphic",
    "prop_or_asset",
    "transition",
    "retention_function",
]


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _parse_beat_visuals(text: str) -> list[BeatVisual]:
    visuals: list[BeatVisual] = []
    blocks = re.split(r"---+", text)
    for block in blocks:
        block_text = block.strip()
        if not block_text:
            continue
        data: dict = {}
        for field in _VISUAL_FIELDS:
            val = _extract_field(block_text, field)
            if val:
                data[field] = val
        if data.get("beat") and data.get("visual"):
            visuals.append(BeatVisual(**data))
    return visuals
