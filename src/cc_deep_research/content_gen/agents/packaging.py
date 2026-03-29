"""Packaging generator agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models import (
    AngleOption,
    PackagingOutput,
    PlatformPackage,
    ScriptVersion,
    StrategyMemory,
)
from cc_deep_research.content_gen.prompts import packaging as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_packaging"


class PackagingAgent:
    """Generate publish-ready packaging variants for each platform."""

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
        script: ScriptVersion,
        angle: AngleOption,
        platforms: list[str],
        *,
        strategy: StrategyMemory | None = None,
        idea_id: str = "",
    ) -> PackagingOutput:
        system = prompts.PACKAGING_SYSTEM
        strat = strategy or StrategyMemory()
        user = prompts.packaging_user(script, angle, platforms, strat)
        text = await self._call_llm(system, user, temperature=0.6)

        packages = _parse_platform_packages(text)
        return PackagingOutput(idea_id=idea_id, platform_packages=packages)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_SCALAR_FIELDS = [
    "platform",
    "primary_hook",
    "cover_text",
    "caption",
    "pinned_comment",
    "cta",
    "version_notes",
]
_LIST_FIELDS = ["alternate_hooks", "keywords", "hashtags"]


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


def _parse_platform_packages(text: str) -> list[PlatformPackage]:
    packages: list[PlatformPackage] = []
    blocks = re.split(r"---+", text)
    for block in blocks:
        block_text = block.strip()
        if not block_text:
            continue
        data: dict = {}
        for field in _SCALAR_FIELDS:
            val = _extract_field(block_text, field)
            if val:
                data[field] = val
        for field in _LIST_FIELDS:
            data[field] = _extract_list(block_text, field)
        if data.get("platform"):
            packages.append(PlatformPackage(**data))
    return packages
