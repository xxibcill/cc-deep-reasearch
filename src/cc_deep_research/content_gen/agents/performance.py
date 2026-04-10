"""Performance analyst agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Any

from cc_deep_research.content_gen.models import PerformanceAnalysis
from cc_deep_research.content_gen.prompts import performance as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_performance"


class PerformanceAgent:
    """Analyze post-publish performance and generate follow-up ideas."""

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
        temperature: float = 0.4,
    ) -> str:
        response = await self._router.execute(
            AGENT_ID,
            user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return response.content

    async def analyze(
        self,
        *,
        video_id: str,
        metrics: dict[str, Any],
        script: str = "",
        hook: str = "",
        caption: str = "",
    ) -> PerformanceAnalysis:
        system = prompts.PERFORMANCE_SYSTEM
        user = prompts.performance_user(
            video_id=video_id,
            metrics=metrics,
            script=script,
            hook=hook,
            caption=caption,
        )
        text = await self._call_llm(system, user, temperature=0.4)

        return _parse_performance(text, video_id)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_LIST_FIELDS = [
    "what_worked",
    "what_failed",
    "audience_signals",
    "dropoff_hypotheses",
    "follow_up_ideas",
    "backlog_updates",
]


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


def _parse_performance(text: str, video_id: str) -> PerformanceAnalysis:
    data: dict[str, Any] = {"video_id": video_id}
    for field in _LIST_FIELDS:
        data[field] = _extract_list(text, field)
    for field in ("hook_diagnosis", "lesson", "next_test"):
        data[field] = _extract_field(text, field)
    return PerformanceAnalysis(**data)
