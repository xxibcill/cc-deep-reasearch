"""Backlog chat agent for conversational backlog refinement."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from cc_deep_research.content_gen.agents._llm_utils import call_agent_llm_text
from cc_deep_research.content_gen.backlog_service import BacklogService
from cc_deep_research.content_gen.models import BacklogItem
from cc_deep_research.content_gen.prompts import backlog_chat as prompts
from cc_deep_research.llm import LLMRouter

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

AGENT_ID = "content_gen_backlog_chat"


class BacklogChatOperation(BaseModel):
    """A single backlog operation proposed by the chat agent."""

    kind: Literal["update_item", "create_item"]
    idea_id: str | None = None
    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class BacklogChatResponse(BaseModel):
    """Structured response from the backlog chat agent."""

    reply_markdown: str
    apply_ready: bool
    warnings: list[str] = Field(default_factory=list)
    operations: list[BacklogChatOperation] = Field(default_factory=list)
    mentioned_idea_ids: list[str] = Field(default_factory=list)


class BacklogChatAgent:
    """Conversational editorial assistant for backlog refinement."""

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
            workflow_name="backlog chat",
            cli_command="content-gen backlog-chat",
            logger=logger,
            allow_blank=False,
        )

    async def respond(
        self,
        messages: list[dict[str, str]],
        backlog_items: list[BacklogItem],
        *,
        strategy: dict[str, Any] | None = None,
        selected_idea_id: str | None = None,
    ) -> BacklogChatResponse:
        """Generate a conversational response with optional backlog operations.

        Args:
            messages: Conversation history as [{"role": "user"|"assistant", "content": str}]
            backlog_items: Current backlog snapshot
            strategy: Optional strategy context
            selected_idea_id: Optional currently selected idea ID

        Returns:
            BacklogChatResponse with reply, operations, and metadata
        """
        system = prompts.BACKLOG_CHAT_SYSTEM
        user = prompts.build_backlog_chat_user(
            messages=messages,
            backlog_items=backlog_items,
            strategy=strategy,
            selected_idea_id=selected_idea_id,
        )

        try:
            text = await self._call_llm(system, user, temperature=0.5)
            parsed = _parse_chat_response(text)

            # Validate mentioned_idea_ids are actually in the backlog
            valid_ids = {item.idea_id for item in backlog_items}
            validated_mentioned = [
                idea_id for idea_id in parsed.get("mentioned_idea_ids", [])
                if idea_id in valid_ids
            ]

            operations = _validate_operations(
                parsed.get("operations", []),
                backlog_items,
            )

            warnings = list(parsed.get("warnings", []))
            if operations:
                _check_duplicate_warnings(operations, backlog_items, warnings)

            return BacklogChatResponse(
                reply_markdown=parsed.get("reply_markdown", "I understand."),
                apply_ready=bool(operations),
                warnings=warnings,
                operations=operations,
                mentioned_idea_ids=validated_mentioned,
            )

        except Exception as exc:
            logger.warning("Backlog chat LLM call failed: %s", exc)
            return BacklogChatResponse(
                reply_markdown=(
                    "I had trouble generating a proposal just now. "
                    "Feel free to try again or describe what you'd like to change."
                ),
                apply_ready=False,
                warnings=[f"LLM call failed: {exc}"],
                operations=[],
                mentioned_idea_ids=[],
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
        # Return safe fallback - no structured operations, just a reply
        return {
            "reply_markdown": text.strip()[:500] if text.strip() else "I understand.",
            "apply_ready": False,
            "warnings": ["Failed to parse structured output from LLM"],
            "operations": [],
            "mentioned_idea_ids": [],
        }

    # Ensure required top-level keys exist
    result: dict[str, Any] = {
        "reply_markdown": str(parsed.get("reply_markdown", ""))[:1000] or "I understand.",
        "apply_ready": bool(parsed.get("apply_ready", False)),
        "warnings": list(parsed.get("warnings", [])),
        "operations": list(parsed.get("operations", [])),
        "mentioned_idea_ids": list(parsed.get("mentioned_idea_ids", [])),
    }

    return result


# ---------------------------------------------------------------------------
# Operation validation
# ---------------------------------------------------------------------------


def _validate_operations(
    operations: list[dict[str, Any]],
    backlog_items: list[BacklogItem],
) -> list[BacklogChatOperation]:
    """Validate and normalize operations from LLM output."""
    validated: list[BacklogChatOperation] = []
    existing_ids = {item.idea_id for item in backlog_items}

    for op in operations:
        if not isinstance(op, dict):
            continue

        kind = op.get("kind", "")
        if kind not in ("update_item", "create_item"):
            continue

        if kind == "update_item":
            idea_id = op.get("idea_id")
            if not idea_id or idea_id not in existing_ids:
                continue
            fields = _sanitize_update_fields(op.get("fields", {}))
            if not fields:
                continue
            validated.append(BacklogChatOperation(
                kind="update_item",
                idea_id=idea_id,
                reason=str(op.get("reason", ""))[:500],
                fields=fields,
            ))

        elif kind == "create_item":
            fields = _sanitize_create_fields(op.get("fields", {}))
            if not fields.get("idea"):
                continue
            validated.append(BacklogChatOperation(
                kind="create_item",
                idea_id=None,
                reason=str(op.get("reason", ""))[:500],
                fields=fields,
            ))

    return validated


def _sanitize_update_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Remove invalid fields from update operation."""
    from cc_deep_research.content_gen.prompts.backlog_chat import SUPPORTED_UPDATE_FIELDS
    return {
        k: str(v)[:2000]
        for k, v in fields.items()
        if k in SUPPORTED_UPDATE_FIELDS and v
    }


def _sanitize_create_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Remove invalid fields from create operation."""
    from cc_deep_research.content_gen.prompts.backlog_chat import SUPPORTED_CREATE_FIELDS
    return {
        k: str(v)[:2000]
        for k, v in fields.items()
        if k in SUPPORTED_CREATE_FIELDS and v
    }


def _check_duplicate_warnings(
    operations: list[BacklogChatOperation],
    backlog_items: list[BacklogItem],
    warnings: list[str],
) -> None:
    """Check for potential duplicate ideas and add warnings."""
    existing_by_idea: dict[str, BacklogItem] = {item.idea: item for item in backlog_items if item.idea}

    for op in operations:
        if op.kind == "create_item":
            new_idea = op.fields.get("idea", "").lower().strip()
            if new_idea in existing_by_idea:
                existing = existing_by_idea[new_idea]
                warnings.append(
                    f"create_item may duplicate existing idea '{existing.idea_id}': {new_idea[:50]}"
                )


# ---------------------------------------------------------------------------
# Apply helpers (used by router)
# ---------------------------------------------------------------------------


async def apply_operations(
    operations: list[BacklogChatOperation],
    service: BacklogService,
) -> tuple[int, list[BacklogItem], list[str]]:
    """Apply a list of validated operations through BacklogService.

    Args:
        operations: List of validated operations to apply
        service: BacklogService instance

    Returns:
        Tuple of (applied_count, list of modified/created items, list of errors)
    """
    applied = 0
    items: list[BacklogItem] = []
    errors: list[str] = []

    for op in operations:
        try:
            if op.kind == "update_item" and op.idea_id:
                updated = service.update_item(op.idea_id, op.fields)
                if updated:
                    applied += 1
                    items.append(updated)
                else:
                    errors.append(f"update_item {op.idea_id}: item not found")
            elif op.kind == "create_item":
                created = service.create_item(
                    idea=op.fields.get("idea", ""),
                    category=op.fields.get("category", ""),
                    audience=op.fields.get("audience", ""),
                    problem=op.fields.get("problem", ""),
                )
                applied += 1
                items.append(created)
        except Exception as exc:
            errors.append(f"{op.kind} {op.idea_id or 'create'}: {exc}")

    return applied, items, errors
