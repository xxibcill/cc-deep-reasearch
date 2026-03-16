"""CLI command registration for CC Deep Research."""

from __future__ import annotations

import subprocess

import click

from cc_deep_research.__about__ import __version__
from cc_deep_research.config import Config
from cc_deep_research.telemetry import ingest_telemetry_to_duckdb

from .benchmark import register_benchmark_commands
from .config import register_config_commands
from .dashboard import register_dashboard_command
from .render import register_render_commands
from .research import register_research_commands
from .session import register_session_commands
from .telemetry import register_telemetry_commands


@click.group()
@click.version_option(version=__version__, prog_name="cc-deep-research")
@click.pass_context
def main(ctx: click.Context) -> None:
    """CC Deep Research - comprehensive web research CLI tool."""
    ctx.ensure_object(dict)


register_research_commands(main)
register_render_commands(main)
register_benchmark_commands(main)
register_config_commands(main)
register_telemetry_commands(main)
register_dashboard_command(main)
register_session_commands(main)

__all__ = ["Config", "ingest_telemetry_to_duckdb", "main", "subprocess"]
