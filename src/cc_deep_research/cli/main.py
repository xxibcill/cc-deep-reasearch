"""CLI command registration for CC Deep Research."""

from __future__ import annotations

import subprocess

import click

from cc_deep_research.__about__ import __version__
from cc_deep_research.config import Config
from cc_deep_research.content_gen import register_content_gen_commands
from cc_deep_research.llm.env import load_env_from_project_root
from cc_deep_research.telemetry import ingest_telemetry_to_duckdb

from .anthropic import register_anthropic_commands
from .benchmark import register_benchmark_commands
from .config import register_config_commands
from .dashboard import register_dashboard_command
from .render import register_render_commands
from .research import register_research_commands
from .session import register_session_commands
from .telemetry import register_telemetry_commands
from .themes import register_themes_commands

# Load .env at startup (does not override existing env vars)
load_env_from_project_root()


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
register_anthropic_commands(main)
register_themes_commands(main)
register_content_gen_commands(main)  # type: ignore[no-untyped-call]

__all__ = ["Config", "ingest_telemetry_to_duckdb", "main", "subprocess"]
