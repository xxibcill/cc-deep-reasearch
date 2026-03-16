"""Shared configuration normalization for research-run requests."""

from __future__ import annotations

from cc_deep_research.config import Config
from cc_deep_research.research_runs.models import ResearchRunRequest


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

