"""Stateless, tool-disabled turn execution for the Codex provider."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from openai_codex import ApprovalMode, Sandbox
from openai_codex.types import ReasoningEffort

from cc_deep_research.llm.codex_security import PROVIDER_INSTRUCTIONS, provider_config
from cc_deep_research.llm.codex_types import CodexRuntimeError, CodexTurnResult

_TURN_INTERRUPT_TIMEOUT_SECONDS = 5.0


async def execute_codex_turn(
    client: Any,
    *,
    cwd: Path,
    prompt: str,
    model: str | None,
    default_model: str | None,
    developer_instructions: str | None,
    reasoning_effort: str | None,
    timeout_seconds: int,
) -> CodexTurnResult:
    """Execute one provider turn without owning client lifecycle decisions."""
    effort = ReasoningEffort(reasoning_effort) if reasoning_effort else None
    instructions = _compose_developer_instructions(developer_instructions)
    started_at = time.perf_counter()
    turn: Any | None = None

    try:
        async with asyncio.timeout(timeout_seconds):
            thread = await client.thread_start(
                approval_mode=ApprovalMode.deny_all,
                base_instructions=PROVIDER_INSTRUCTIONS,
                config=provider_config(),
                cwd=str(cwd),
                developer_instructions=instructions,
                ephemeral=True,
                model=model,
                sandbox=Sandbox.read_only,
            )
            turn = await thread.turn(
                prompt,
                approval_mode=ApprovalMode.deny_all,
                cwd=str(cwd),
                effort=effort,
                model=model,
                sandbox=Sandbox.read_only,
            )
            result = await turn.run()
    except (TimeoutError, asyncio.CancelledError):
        if turn is not None:
            await _interrupt_turn(turn)
        raise

    turn_status = _enum_value(result.status)
    if turn_status != "completed":
        raise CodexRuntimeError(
            f"Codex turn did not complete successfully (status={turn_status or 'unknown'})"
        )
    if not result.final_response:
        raise CodexRuntimeError("Codex turn completed without a final response")

    usage = getattr(result, "usage", None)
    last_usage = getattr(usage, "last", None)
    duration_ms = result.duration_ms
    if duration_ms is None:
        duration_ms = int((time.perf_counter() - started_at) * 1000)

    return CodexTurnResult(
        content=result.final_response,
        model=model or default_model or "codex-default",
        turn_id=result.id,
        duration_ms=duration_ms,
        finish_reason="completed",
        input_tokens=int(getattr(last_usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(last_usage, "output_tokens", 0) or 0),
        total_tokens=int(getattr(last_usage, "total_tokens", 0) or 0),
        cached_input_tokens=int(getattr(last_usage, "cached_input_tokens", 0) or 0),
        reasoning_output_tokens=int(getattr(last_usage, "reasoning_output_tokens", 0) or 0),
    )


def _compose_developer_instructions(value: str | None) -> str:
    if not value:
        return PROVIDER_INSTRUCTIONS
    return f"{value.rstrip()}\n\n{PROVIDER_INSTRUCTIONS}"


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


async def _interrupt_turn(turn: Any) -> None:
    task = asyncio.create_task(turn.interrupt())
    try:
        await asyncio.wait_for(
            asyncio.shield(task),
            timeout=_TURN_INTERRUPT_TIMEOUT_SECONDS,
        )
    except BaseException:
        task.cancel()
        with suppress(BaseException):
            await task


__all__ = ["execute_codex_turn"]
