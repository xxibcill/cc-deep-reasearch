"""Shared LLM call hardening for content-generation agents."""

from __future__ import annotations

import logging

from cc_deep_research.llm import LLMRouter


def _missing_route_message(*, workflow_name: str, cli_command: str) -> str:
    return (
        f"No LLM route is available for the {workflow_name}. "
        "Enable Anthropic, OpenRouter, or Cerebras with API keys before running "
        f"'{cli_command}'."
    )


async def call_agent_llm_text(
    *,
    router: LLMRouter,
    agent_id: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    workflow_name: str,
    cli_command: str,
    logger: logging.Logger | None = None,
    allow_blank: bool = False,
    max_attempts: int = 2,
) -> str:
    """Execute an agent LLM call with route checks and bounded empty-response retry."""
    if not router.is_available(agent_id):
        raise RuntimeError(_missing_route_message(workflow_name=workflow_name, cli_command=cli_command))

    for attempt in range(1, max_attempts + 1):
        response = await router.execute(
            agent_id,
            user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        text = response.content.strip()
        if text:
            return response.content
        if logger is not None:
            logger.warning(
                "%s returned empty content on attempt %d/%d via %s",
                workflow_name,
                attempt,
                max_attempts,
                response.transport.value,
            )

    if allow_blank:
        return ""

    raise ValueError(
        f"{workflow_name} returned an empty response from the LLM after {max_attempts} attempt(s)."
    )


__all__ = ["call_agent_llm_text"]
