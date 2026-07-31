"""Publish queue agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import (
    call_agent_llm_text,
    create_agent_llm_router,
)
from cc_deep_research.content_gen.models import (
    PackagingOutput,
    PublishItem,
)
from cc_deep_research.content_gen.prompts import publish as prompts

if TYPE_CHECKING:
    from cc_deep_research.config import Config
    from cc_deep_research.llm.runtime_context import LLMRuntimeContext

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_publish"


class PublishAgent:
    """Create publish queue entries with engagement plans."""

    def __init__(
        self,
        config: Config,
        *,
        llm_runtime: LLMRuntimeContext | None = None,
    ) -> None:
        self._config = config
        self._router = create_agent_llm_router(config, llm_runtime=llm_runtime)

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
            workflow_name="publish queue workflow",
            cli_command="content-gen publish schedule",
            logger=logger,
            allow_blank=True,
        )

    async def schedule(
        self,
        packaging: PackagingOutput,
        *,
        idea_id: str = "",
        platforms: list[str] | None = None,
    ) -> list[PublishItem]:
        items: list[PublishItem] = []
        target_platforms = platforms or self._config.content_gen.default_platforms

        for pkg in packaging.platform_packages:
            system = prompts.PUBLISH_SYSTEM
            user = prompts.publish_user(pkg.platform, pkg.caption, pkg.cta)
            text = await self._call_llm(system, user, temperature=0.3)

            datetime = _extract_field(text, "publish_datetime")
            plan = _extract_field(text, "first_30_minute_engagement_plan")

            items.append(
                PublishItem(
                    idea_id=idea_id,
                    platform=pkg.platform,
                    publish_datetime=datetime,
                    caption_version=pkg.caption[:100],
                    pinned_comment=pkg.pinned_comment,
                    cross_post_targets=[p for p in target_platforms if p != pkg.platform],
                    first_30_minute_engagement_plan=plan,
                )
            )
        return items


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""
