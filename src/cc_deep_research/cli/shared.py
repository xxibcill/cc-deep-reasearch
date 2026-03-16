"""Shared CLI helpers used by command registration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import click

from cc_deep_research.config import Config, load_config
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.tui import TerminalUI

RESEARCH_PHASE_STEPS = 8


def execute_research_run(
    *,
    orchestrator: Any,
    query: str,
    depth: Any,
    min_sources: int | None,
    progress: bool,
    ui: TerminalUI,
) -> Any:
    """Run the orchestrator and optionally render phase progress."""
    if progress:
        with ui.create_phase_progress(RESEARCH_PHASE_STEPS) as tracker:
            session = asyncio.run(
                orchestrator.execute_research(
                    query=query,
                    depth=depth,
                    min_sources=min_sources,
                    phase_hook=tracker.on_phase,
                )
            )
            tracker.mark_complete()
            return session

    with ui.status("Running research workflow..."):
        return asyncio.run(
            orchestrator.execute_research(
                query=query,
                depth=depth,
                min_sources=min_sources,
            )
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


def resolve_config_target(config_obj: Config, key: str) -> tuple[Any, str]:
    """Resolve object and attribute for a dot-notation configuration key."""
    key_parts = key.split(".")
    target: Any = config_obj

    for part in key_parts[:-1]:
        if not hasattr(target, part):
            click.echo(f"Error: Invalid configuration key: {key}", err=True)
            raise click.Abort()
        target = getattr(target, part)

    final_key = key_parts[-1]
    if not hasattr(target, final_key):
        click.echo(f"Error: Invalid configuration key: {key}", err=True)
        raise click.Abort()

    return target, final_key


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


__all__ = [
    "RESEARCH_PHASE_STEPS",
    "describe_execution_mode",
    "execute_research_run",
    "format_config_value",
    "load_config_from_path",
    "log_monitor_session_start",
    "parse_config_value",
    "resolve_config_target",
    "resolve_parallel_mode_override",
]
