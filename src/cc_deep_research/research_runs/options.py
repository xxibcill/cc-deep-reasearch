"""Shared configuration normalization for research-run requests."""

from __future__ import annotations

from dataclasses import dataclass

from cc_deep_research.config import Config
from cc_deep_research.prompts import PromptRegistry
from cc_deep_research.research_runs.models import ResearchRunRequest


@dataclass(slots=True)
class ResearhRunContext:
    """Runtime context for a research run execution.

    Attributes:
        config: The resolved configuration.
        prompt_registry: The prompt registry with overrides applied.
    """

    config: Config
    prompt_registry: PromptRegistry


def apply_research_request_config_overrides(
    config: Config,
    request: ResearchRunRequest,
) -> Config:
    """Return a config copy with request overrides applied."""
    updated = config.model_copy(deep=True)

    if request.team_size is not None:
        updated.search_team.team_size = request.team_size

    if request.cross_reference_enabled is not None:
        updated.research.enable_cross_ref = request.cross_reference_enabled

    if request.search_providers is not None:
        updated.search.providers = request.search_providers

    if request.parallel_mode is not None:
        updated.search_team.parallel_execution = request.parallel_mode

    return updated


def create_prompt_registry_with_overrides(
    request: ResearchRunRequest,
) -> PromptRegistry:
    """Create a prompt registry with request overrides applied.

    Args:
        request: The research run request containing prompt overrides.

    Returns:
        A PromptRegistry with overrides applied.
    """
    registry = PromptRegistry()
    registry.apply_raw_overrides(request.agent_prompt_overrides)
    return registry


def build_research_run_context(
    config: Config,
    request: ResearchRunRequest,
) -> ResearhRunContext:
    """Build the complete runtime context for a research run.

    Args:
        config: The base configuration.
        request: The research run request.

    Returns:
        ResearhRunContext with resolved config and prompt registry.
    """
    resolved_config = apply_research_request_config_overrides(config, request)
    prompt_registry = create_prompt_registry_with_overrides(request)
    return ResearhRunContext(
        config=resolved_config,
        prompt_registry=prompt_registry,
    )

