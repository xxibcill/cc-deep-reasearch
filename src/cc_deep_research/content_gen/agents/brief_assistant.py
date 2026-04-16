"""Brief assistant agent for conversational brief refinement."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.models import BriefRevision
from cc_deep_research.content_gen.prompts import brief_assistant as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_brief_assistant"


class BriefAssistantProposal(BaseModel):
    """A single brief revision proposal from the assistant."""

    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class BriefAssistantResponse(BaseModel):
    """Structured response from the brief assistant."""

    reply_markdown: str
    apply_ready: bool
    warnings: list[str] = Field(default_factory=list)
    proposals: list[BriefAssistantProposal] = Field(default_factory=list)
    mentioned_fields: list[str] = Field(default_factory=list)


BriefAssistantMode = Literal["conversation", "edit"]


class BriefAssistantAgent:
    """Conversational editorial assistant for brief refinement."""

    def __init__(self, config: Config | None = None) -> None:
        from cc_deep_research.llm.registry import LLMRouteRegistry

        if config is None:
            from cc_deep_research.config import load_config

            config = load_config()

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
            workflow_name="brief assistant",
            cli_command="content-gen brief-assistant",
            logger=logger,
            allow_blank=False,
        )

    async def respond(
        self,
        messages: list[dict[str, str]],
        brief_revision: BriefRevision | None,
        *,
        mode: BriefAssistantMode = "edit",
    ) -> BriefAssistantResponse:
        """Generate a conversational response with optional brief revision proposals.

        Args:
            messages: Conversation history as [{"role": "user"|"assistant", "content": str}]
            brief_revision: Current brief revision snapshot
            mode: Response mode ("conversation" or "edit")

        Returns:
            BriefAssistantResponse with reply, proposals, and metadata
        """
        system = (
            prompts.BRIEF_ASSISTANT_CONVERSATION_SYSTEM
            if mode == "conversation"
            else prompts.BRIEF_ASSISTANT_EDIT_SYSTEM
        )
        user = prompts.build_brief_assistant_user(
            messages=messages,
            brief_revision=brief_revision,
            mode=mode,
        )

        try:
            text = await self._call_llm(system, user, temperature=0.5)
            parsed = _parse_chat_response(text)

            warnings = list(parsed.get("warnings", []))
            proposals = []
            if mode == "edit":
                proposals = _validate_proposals(parsed.get("proposals", []))

            return BriefAssistantResponse(
                reply_markdown=parsed.get("reply_markdown", "I understand."),
                apply_ready=mode == "edit" and bool(proposals),
                warnings=warnings,
                proposals=proposals,
                mentioned_fields=list(parsed.get("mentioned_fields", [])),
            )

        except Exception as exc:
            logger.warning("Brief assistant LLM call failed: %s", exc)
            return BriefAssistantResponse(
                reply_markdown=(
                    "I had trouble generating a proposal just now. "
                    "Feel free to try again or describe what you'd like to change."
                ),
                apply_ready=False,
                warnings=[f"LLM call failed: {exc}"],
                proposals=[],
                mentioned_fields=[],
            )


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Extract JSON object from text, handling code fences and partial output."""
    text = text.strip()

    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    fence_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
    for match in fence_pattern.finditer(text):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # Try finding a JSON object anywhere in the text
    json_start = text.find("{")
    if json_start != -1:
        # Find the matching closing brace
        depth = 0
        for i, ch in enumerate(text[json_start:], start=json_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[json_start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    return None


def _parse_chat_response(text: str) -> dict[str, Any]:
    """Parse LLM output into a dict, with graceful fallback."""
    parsed = _extract_json_from_text(text)
    if parsed is None:
        # Return safe fallback - no structured proposals, just a reply
        return {
            "reply_markdown": text.strip()[:500] if text.strip() else "I understand.",
            "apply_ready": False,
            "warnings": ["Failed to parse structured output from LLM"],
            "proposals": [],
            "mentioned_fields": [],
        }

    # Ensure required top-level keys exist
    raw_reply = str(parsed.get("reply_markdown", "") or "I understand.")
    if len(raw_reply) > 1000:
        logger.warning("Brief assistant reply truncated from %d to 1000 chars", len(raw_reply))
    result: dict[str, Any] = {
        "reply_markdown": raw_reply[:1000],
        "apply_ready": bool(parsed.get("apply_ready", False)),
        "warnings": list(parsed.get("warnings", [])),
        "proposals": list(parsed.get("proposals", [])),
        "mentioned_fields": list(parsed.get("mentioned_fields", [])),
    }

    return result


# ---------------------------------------------------------------------------
# Proposal validation
# ---------------------------------------------------------------------------


def _validate_proposals(proposals: list[dict[str, Any]]) -> list[BriefAssistantProposal]:
    """Validate and normalize proposals from LLM output."""
    validated: list[BriefAssistantProposal] = []

    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue

        fields = _sanitize_revision_fields(proposal.get("fields", {}))
        if not fields:
            continue

        validated.append(
            BriefAssistantProposal(
                reason=str(proposal.get("reason", ""))[:500],
                fields=fields,
            )
        )

    return validated


def _sanitize_revision_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Remove invalid fields from revision proposal."""
    from cc_deep_research.content_gen.prompts.brief_assistant import SUPPORTED_REVISION_FIELDS

    result: dict[str, Any] = {}
    for key, value in fields.items():
        if key in SUPPORTED_REVISION_FIELDS:
            # Handle list fields
            if key in (
                "secondary_audience_segments",
                "problem_statements",
                "proof_requirements",
                "platform_constraints",
                "risk_constraints",
                "sub_angles",
                "research_hypotheses",
                "success_criteria",
                "non_obvious_claims_to_test",
                "genericity_risks",
            ):
                if isinstance(value, list):
                    result[key] = [str(v)[:500] for v in value if v]
                elif isinstance(value, str):
                    # Support comma-separated values
                    result[key] = [v.strip() for v in value.split(",") if v.strip()]
            else:
                result[key] = str(value)[:2000] if value else ""

    return result


def build_apply_proposals(
    proposals: list[dict[str, Any]],
) -> tuple[list[BriefAssistantProposal], list[str]]:
    """Validate client-submitted proposals using the same rules as LLM output."""
    validated: list[BriefAssistantProposal] = []
    errors: list[str] = []

    for index, proposal in enumerate(proposals, start=1):
        if not isinstance(proposal, dict):
            errors.append(f"Proposal {index}: invalid payload")
            continue

        fields = _sanitize_revision_fields(proposal.get("fields", {}))
        if not fields:
            errors.append(f"Proposal {index}: no supported fields")
            continue

        validated.append(
            BriefAssistantProposal(
                reason=str(proposal.get("reason", ""))[:500],
                fields=fields,
            )
        )

    return validated, errors
