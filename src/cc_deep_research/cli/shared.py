"""Shared CLI helpers used by command registration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import click

from cc_deep_research.config import Config, ConfigPatchError, load_config, resolve_config_target
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.research_runs import ResearchRunRequest, ResearchTheme, ResearchWorkflow
from cc_deep_research.tui import TerminalUI

RESEARCH_PHASE_STEPS = 8


class TerminalResearchRunExecutionAdapter:
    """Execute a shared research run while preserving terminal UX."""

    def __init__(
        self,
        *,
        progress: bool,
        ui: TerminalUI,
    ) -> None:
        self._progress = progress
        self._ui = ui

    def execute(self, *, execute_with_phase_hook: Any) -> Any:
        """Run the workflow with terminal progress or a plain status message."""
        if self._progress:
            with self._ui.create_phase_progress(RESEARCH_PHASE_STEPS) as tracker:
                session = asyncio.run(execute_with_phase_hook(tracker.on_phase))
                tracker.mark_complete()
                return session

        with self._ui.status("Running research workflow..."):
            return asyncio.run(execute_with_phase_hook(None))


def build_research_run_request(
    *,
    query: str,
    depth: Any,
    min_sources: int | None,
    output: str | None,
    output_format: str,
    no_cross_ref: bool,
    tavily_only: bool,
    claude_only: bool,
    no_team: bool,
    team_size: int | None,
    parallel_mode: bool,
    num_researchers: int | None,
    enable_realtime: bool,
    pdf: bool,
    workflow: str = "staged",
    theme: ResearchTheme | None = None,
) -> ResearchRunRequest:
    """Translate CLI flags into the shared research-run request."""
    return ResearchRunRequest(
        query=query,
        depth=depth,
        min_sources=min_sources,
        output_path=output,
        output_format=output_format,
        search_providers=_resolve_provider_override(
            tavily_only=tavily_only,
            claude_only=claude_only,
        ),
        cross_reference_enabled=False if no_cross_ref else None,
        team_size=team_size,
        parallel_mode=resolve_parallel_mode_override(
            no_team=no_team,
            parallel_mode=parallel_mode,
        ),
        num_researchers=num_researchers,
        realtime_enabled=enable_realtime,
        pdf_enabled=pdf,
        workflow=ResearchWorkflow(workflow.lower()),
        theme=theme,
    )


def resolve_parallel_mode_override(*, no_team: bool, parallel_mode: bool) -> bool | None:
    """Resolve the effective parallel override passed to the orchestrator."""
    if no_team:
        return False
    if parallel_mode:
        return True
    return None


def describe_execution_mode(config: Config, parallel_mode_override: bool | None) -> str:
    """Describe execution mode for display."""
    parallel_enabled = (
        parallel_mode_override
        if parallel_mode_override is not None
        else config.search_team.parallel_execution
    )
    return "parallel" if parallel_enabled else "sequential"


def log_monitor_session_start(
    research_monitor: ResearchMonitor,
    *,
    query: str,
    depth: str,
    output_format: str,
    config: Config,
) -> None:
    """Emit monitor startup metadata."""
    research_monitor.section("Research Session")
    research_monitor.log(f"Query: {query}")
    research_monitor.log(f"Depth: {depth}")
    research_monitor.log(f"Output format: {output_format}")

    research_monitor.section("Configuration")
    research_monitor.log(f"Providers: {', '.join(config.search.providers)}")
    research_monitor.log(f"Search depth: {config.search.depth}")
    research_monitor.log(f"Search mode: {config.search.mode}")
    research_monitor.log(
        "Source collection: "
        + ("parallel" if config.search_team.parallel_execution else "sequential")
    )

    research_monitor.section("Execution")


def load_config_from_path(config_path: str | None) -> Config:
    """Load configuration from default location or a provided path."""
    if config_path is None:
        return load_config()
    return load_config(Path(config_path))


def resolve_cli_config_target(config_obj: Config, key: str) -> tuple[Any, str]:
    """Resolve a config target for CLI usage with click-friendly errors."""
    try:
        return resolve_config_target(config_obj, key)
    except ConfigPatchError as error:
        click.echo(f"Error: {error.message}", err=True)
        raise click.Abort() from error


def parse_config_value(current_value: Any, value: str, key: str) -> Any:
    """Parse CLI string values into the target config field type."""
    if isinstance(current_value, list):
        return [item.strip() for item in value.split(",") if item.strip()]

    if isinstance(current_value, bool):
        return value.lower() in {"true", "1", "yes", "on"}

    if isinstance(current_value, int):
        try:
            return int(value)
        except ValueError as error:
            click.echo(f"Error: Expected integer value for {key}, got: {value}", err=True)
            raise click.Abort() from error

    return value


def format_config_value(value: Any) -> str:
    """Format config values for display."""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


def _resolve_provider_override(*, tavily_only: bool, claude_only: bool) -> list[str] | None:
    """Map CLI provider flags to the shared override contract."""
    providers: list[str] | None = None
    if tavily_only:
        providers = ["tavily"]
    if claude_only:
        providers = ["claude"]
    return providers


__all__ = [
    "RESEARCH_PHASE_STEPS",
    "TerminalResearchRunExecutionAdapter",
    "build_research_run_request",
    "describe_execution_mode",
    "format_config_value",
    "load_config_from_path",
    "log_monitor_session_start",
    "parse_config_value",
    "resolve_cli_config_target",
    "resolve_parallel_mode_override",
]
