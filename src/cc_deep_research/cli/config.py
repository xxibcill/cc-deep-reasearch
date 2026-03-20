"""Config command registration."""

from __future__ import annotations

from pathlib import Path

import click

from cc_deep_research.config import (
    ConfigPatchError,
    build_config_response,
    create_default_config_file,
    get_default_config_path,
    update_config,
)
from cc_deep_research.tui import TerminalUI

from .shared import (
    format_config_value,
    load_config_from_path,
    parse_config_value,
    resolve_cli_config_target,
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
        target, final_key = resolve_cli_config_target(config_obj, key)
        parsed_value = parse_config_value(getattr(target, final_key), value, key)

        save_path = Path(config_path) if config_path else get_default_config_path()
        try:
            update_config({key: parsed_value}, config_path=save_path, save_overridden_fields=True)
        except ConfigPatchError as error:
            click.echo(f"Error: {error.message}", err=True)
            raise click.Abort() from error
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
        config_snapshot = build_config_response(Path(config_path) if config_path else None)
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
            ("config.file_exists", str(config_snapshot.file_exists).lower()),
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
