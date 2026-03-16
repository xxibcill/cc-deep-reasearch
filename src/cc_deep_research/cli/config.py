"""Config command registration."""

from __future__ import annotations

from pathlib import Path

import click

from cc_deep_research.config import (
    create_default_config_file,
    get_default_config_path,
    save_config,
)
from cc_deep_research.tui import TerminalUI

from .shared import (
    format_config_value,
    load_config_from_path,
    parse_config_value,
    resolve_config_target,
)


def register_config_commands(cli: click.Group) -> None:
    """Register configuration commands."""

    @cli.group()
    def config() -> None:
        """Manage configuration settings."""

    @config.command()
    @click.argument("key", required=True)
    @click.argument("value", required=True)
    @click.option(
        "--config-path",
        type=click.Path(),
        default=None,
        help="Path to config file (uses default if not specified)",
    )
    def set(key: str, value: str, config_path: str | None) -> None:
        """Set a configuration value."""
        config_obj = load_config_from_path(config_path)
        target, final_key = resolve_config_target(config_obj, key)
        parsed_value = parse_config_value(getattr(target, final_key), value, key)
        setattr(target, final_key, parsed_value)

        save_path = Path(config_path) if config_path else get_default_config_path()
        save_config(config_obj, save_path)
        TerminalUI(enabled=True).show_config_updated(key, str(parsed_value), save_path)

    @config.command()
    @click.option(
        "--config-path",
        type=click.Path(),
        default=None,
        help="Path to config file (uses default if not specified)",
    )
    def show(config_path: str | None) -> None:
        """Show current configuration."""
        config_obj = load_config_from_path(config_path)
        rows = [
            ("search.providers", ", ".join(config_obj.search.providers)),
            ("search.mode", format_config_value(config_obj.search.mode)),
            ("search.depth", format_config_value(config_obj.search.depth)),
            ("tavily.api_keys", f"{len(config_obj.tavily.api_keys)} configured"),
            ("tavily.max_results", str(config_obj.tavily.max_results)),
            ("search_team.enabled", str(config_obj.search_team.enabled).lower()),
            ("search_team.team_size", str(config_obj.search_team.team_size)),
            ("output.format", config_obj.output.format),
            ("output.save_dir", config_obj.output.save_dir),
        ]
        TerminalUI(enabled=True).show_config(rows)

    @config.command()
    @click.option(
        "--config-path",
        type=click.Path(),
        default=None,
        help="Path to config file (uses default if not specified)",
    )
    @click.option("--force", is_flag=True, help="Overwrite existing config file")
    def init(config_path: str | None, force: bool) -> None:
        """Create a default configuration file."""
        save_path = Path(config_path) if config_path else get_default_config_path()
        if save_path.exists() and not force:
            click.echo(
                f"Error: Config file already exists at {save_path}. Use --force to overwrite.",
                err=True,
            )
            raise click.Abort()

        created_path = create_default_config_file(save_path)
        TerminalUI(enabled=True).show_config_updated("config", "initialized", created_path)


__all__ = ["register_config_commands"]
