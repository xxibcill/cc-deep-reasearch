"""Research pack builder agent with search provider integration."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.models import (
    AngleOption,
    BacklogItem,
    ResearchPack,
)
from cc_deep_research.content_gen.prompts import research_pack as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_research"


class ResearchPackAgent:
    """Build a compact research pack using search providers and LLM synthesis."""

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

    async def build(
        self,
        item: BacklogItem,
        angle: AngleOption,
        *,
        max_queries: int | None = None,
        feedback: str = "",
    ) -> ResearchPack:
        max_q = max_queries or self._config.content_gen.research_max_queries
        search_context = await self._run_searches(item, angle, max_queries=max_q)

        system = prompts.SYNTHESIS_SYSTEM
        user = prompts.synthesis_user(item, angle, search_context, feedback=feedback)
        text = await self._call_llm(system, user, temperature=0.3)

        return _parse_research_pack(text, item.idea_id, angle.angle_id)

    async def _run_searches(
        self,
        item: BacklogItem,
        angle: AngleOption,
        *,
        max_queries: int = 6,
    ) -> str:
        queries = _build_search_queries(item, angle)[:max_queries]
        if not queries:
            return "No search queries generated."

        results: list[str] = []
        try:
            providers = self._get_providers()
        except Exception:
            logger.warning("Could not initialize search providers; skipping search")
            return "Search providers unavailable."

        from cc_deep_research.models import SearchOptions

        opts = SearchOptions(max_results=5)
        for provider in providers:
            for query in queries:
                try:
                    result = await provider.search(query, opts)
                    if result and result.items:
                        for r in result.items[:3]:
                            snippet = (
                                f"[{r.title}] {r.content[:300]}" if r.content else f"[{r.title}]"
                            )
                            results.append(snippet)
                except Exception:
                    logger.debug("Search query '%s' failed", query, exc_info=True)

        if not results:
            return "No search results found."
        return "\n".join(results)

    def _get_providers(self) -> list[str]:
        from cc_deep_research.providers import resolve_provider_specs
        from cc_deep_research.providers.factory import build_search_providers

        specs = resolve_provider_specs(self._config)
        providers, _ = build_search_providers(self._config, specs)
        return providers


def _build_search_queries(item: BacklogItem, angle: AngleOption) -> list[str]:
    queries: list[str] = []
    if item.idea:
        queries.append(f"{item.idea} {item.audience} pain points challenges")
    if item.idea:
        queries.append(f"best {item.idea} short form videos")
    if angle.core_promise:
        queries.append(f"{angle.core_promise} evidence research")
    if item.idea:
        queries.append(f"{item.idea} myths misconceptions")
    if angle.viewer_problem:
        queries.append(f"{angle.viewer_problem} solutions")
    if angle.target_audience:
        queries.append(f"{angle.target_audience} content trends 2025")
    return queries


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_LIST_FIELDS = [
    "audience_insights",
    "competitor_observations",
    "key_facts",
    "proof_points",
    "examples",
    "case_studies",
    "gaps_to_exploit",
    "assets_needed",
    "claims_requiring_verification",
    "unsafe_or_uncertain_claims",
]


def _parse_research_pack(text: str, idea_id: str, angle_id: str) -> ResearchPack:
    """Parse research sections.

    This stage is intentionally tolerant: downstream scripting can continue
    with a partial pack, and later iterations may rerun research to fill gaps.
    """
    data: dict[str, Any] = {"idea_id": idea_id, "angle_id": angle_id}
    for field in _LIST_FIELDS:
        data[field] = _extract_list(text, field)
    data["research_stop_reason"] = _extract_field(text, "research_stop_reason")
    return ResearchPack(**data)


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
