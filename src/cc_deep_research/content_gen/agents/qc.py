"""Human QC gate agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import HumanQCGate
from cc_deep_research.content_gen.prompts import qc as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_qc"


class QCAgent:
    """Run AI-assisted QC and produce a human-gateable review.

    This agent never sets ``approved_for_publish`` to ``True``.
    Only a human can approve via the CLI ``content-gen qc approve`` command.
    """

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
        temperature: float = 0.2,
    ) -> str:
        return await call_agent_llm_text(
            router=self._router,
            agent_id=AGENT_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            workflow_name="human QC workflow",
            cli_command="content-gen qc review",
            logger=logger,
        )

    async def review(
        self,
        *,
        script: str,
        visual_summary: str = "",
        packaging_summary: str = "",
        research_summary: str = "",
        argument_map_summary: str = "",
        success_criteria: list[str] | None = None,
    ) -> HumanQCGate:
        system = prompts.QC_SYSTEM
        user = prompts.qc_user(
            script=script,
            visual_summary=visual_summary,
            packaging_summary=packaging_summary,
            research_summary=research_summary,
            argument_map_summary=argument_map_summary,
            success_criteria=success_criteria,
        )
        text = await self._call_llm(system, user, temperature=0.2)

        gate = _parse_qc_gate(text)
        if not gate.hook_strength:
            msg = "Human QC parsing failed: missing required field 'hook_strength'."
            raise ValueError(msg)
        return gate


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


def _parse_qc_gate(text: str) -> HumanQCGate:
    risky_claims = _extract_list(text, "risky_claims")
    must_fix_items = _extract_list(text, "must_fix_items")
    must_fix_items.extend(
        f"Resolve risky claim before publish: {claim}"
        for claim in risky_claims
        if claim and f"Resolve risky claim before publish: {claim}" not in must_fix_items
    )
    return HumanQCGate(
        hook_strength=_extract_field(text, "hook_strength"),
        clarity_issues=_extract_list(text, "clarity_issues"),
        factual_issues=_extract_list(text, "factual_issues"),
        visual_issues=_extract_list(text, "visual_issues"),
        audio_issues=_extract_list(text, "audio_issues"),
        caption_issues=_extract_list(text, "caption_issues"),
        unsupported_claims=_extract_list(text, "unsupported_claims"),
        risky_claims=risky_claims,
        required_fact_checks=_extract_list(text, "required_fact_checks"),
        must_fix_items=must_fix_items,
        success_criteria_results=_extract_list(text, "success_criteria_evaluation"),
    )
