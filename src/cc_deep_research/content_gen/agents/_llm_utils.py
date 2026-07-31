"""Shared LLM call hardening for content-generation agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cc_deep_research.llm import LLMRouter, LLMTransportType

if TYPE_CHECKING:
    from cc_deep_research.config import Config
    from cc_deep_research.llm.codex_runtime import CodexRuntime


def _transport_from_route_name(route_name: str) -> LLMTransportType:
    route_map = {
        "openrouter": LLMTransportType.OPENROUTER_API,
        "cerebras": LLMTransportType.CEREBRAS_API,
        "anthropic": LLMTransportType.ANTHROPIC_API,
        "codex": LLMTransportType.CODEX_APP_SERVER,
        "heuristic": LLMTransportType.HEURISTIC,
    }
    transport = route_map.get(route_name)
    if transport is None:
        raise ValueError(f"Unsupported content-generation LLM route: {route_name}")
    return transport


def create_agent_llm_router(
    config: Config,
    *,
    codex_runtime: CodexRuntime | None = None,
    agent_id: str | None = None,
    llm_route: str | None = None,
) -> LLMRouter:
    """Create a content-agent router with optional route and runtime overrides."""
    from cc_deep_research.llm.registry import LLMRouteRegistry

    registry = LLMRouteRegistry(config.llm)
    if llm_route is not None:
        if agent_id is None:
            raise ValueError("agent_id is required when overriding an LLM route")
        transport = _transport_from_route_name(llm_route)
        registry.set_route(agent_id, registry.get_route_for_transport(transport))
    return LLMRouter(registry, codex_runtime=codex_runtime)


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
        raise RuntimeError(
            _missing_route_message(workflow_name=workflow_name, cli_command=cli_command)
        )

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


__all__ = ["call_agent_llm_text", "create_agent_llm_router"]
