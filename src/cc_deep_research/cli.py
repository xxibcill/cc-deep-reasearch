"""CLI entry point for CC Deep Research."""

import asyncio
from pathlib import Path

import click

from cc_deep_research import __version__
from cc_deep_research.config import (
    Config,
    load_config,
    save_config,
    get_default_config_path,
)


@click.group()
@click.version_option(version=__version__, prog_name="cc-deep-research")
@click.pass_context
def main(ctx: click.Context) -> None:
    """CC Deep Research - Comprehensive web research CLI tool.

    Perform deep research using Tavily Search API and Claude Code's
    built-in search capabilities.
    """
    ctx.ensure_object(dict)


@main.command()
@click.argument("query", required=True)
@click.option(
    "-d",
    "--depth",
    type=click.Choice(["quick", "standard", "deep"], case_sensitive=False),
    default="deep",
    help="Research depth mode (default: deep)",
)
@click.option(
    "-s",
    "--sources",
    "min_sources",
    type=int,
    default=None,
    help="Minimum number of sources to gather",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Output file path for the report",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option("--no-cross-ref", is_flag=True, help="Disable cross-reference analysis")
@click.option("--tavily-only", is_flag=True, help="Use only Tavily provider")
@click.option("--claude-only", is_flag=True, help="Use only Claude provider")
@click.option("--no-team", is_flag=True, help="Disable agent teams, use sequential mode")
@click.option("--team-size", "team_size", type=int, default=None, help="Override default team size")
@click.option("--progress", is_flag=True, default=True, help="Show progress indicators")
@click.option("--quiet", is_flag=True, help="Suppress output")
@click.option("--verbose", is_flag=True, help="Show detailed output")
@click.option("--monitor", is_flag=True, help="Show internal workflow monitoring information")
@click.pass_context
def research(
    ctx: click.Context,
    query: str,
    depth: str,
    min_sources: int | None,
    output: str | None,
    output_format: str,
    no_cross_ref: bool,
    tavily_only: bool,
    claude_only: bool,
    no_team: bool,
    team_size: int | None,
    progress: bool,
    quiet: bool,
    verbose: bool,
    monitor: bool,
) -> None:
    """Execute a research query and generate a report.

    QUERY is the research topic or question to investigate.
    """
    # Store options in context for potential use by subcommands
    ctx.obj["query"] = query
    ctx.obj["depth"] = depth
    ctx.obj["min_sources"] = min_sources
    ctx.obj["output"] = output
    ctx.obj["output_format"] = output_format
    ctx.obj["no_cross_ref"] = no_cross_ref
    ctx.obj["tavily_only"] = tavily_only
    ctx.obj["claude_only"] = claude_only
    ctx.obj["no_team"] = no_team
    ctx.obj["team_size"] = team_size
    ctx.obj["progress"] = progress
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose
    ctx.obj["monitor"] = monitor

    if verbose:
        click.echo(f"Research query: {query}")
        click.echo(f"Depth: {depth}")
        click.echo(f"Output format: {output_format}")
        if no_team:
            click.echo("Mode: Sequential (agent teams disabled)")
        else:
            click.echo(f"Mode: Agent Teams (size: {team_size or 'default'})")

    # Initialize monitoring if enabled
    from cc_deep_research.monitoring import ResearchMonitor

    research_monitor = ResearchMonitor(enabled=monitor and not quiet)

    if monitor and not quiet:
        research_monitor.section("Research Session")
        research_monitor.log(f"Query: {query}")
        research_monitor.log(f"Depth: {depth}")
        research_monitor.log(f"Output format: {output_format}")

        # Log configuration
        research_monitor.section("Configuration")
        from cc_deep_research.config import load_config

        config_obj = load_config()
        research_monitor.log(f"Providers: {', '.join(config_obj.search.providers)}")
        research_monitor.log(f"Search depth: {config_obj.search.depth}")
        research_monitor.log(f"Search mode: {config_obj.search.mode}")
        research_monitor.log(f"Agent teams: {'enabled' if config_obj.search_team.enabled else 'disabled'}")

        research_monitor.section("Execution")

    # Execute research using agent teams
    try:
        from cc_deep_research.models import ResearchDepth
        from cc_deep_research.orchestrator import TeamResearchOrchestrator
        from cc_deep_research.reporting import ReportGenerator

        # Load configuration
        config = load_config()

        # Override team settings from CLI options
        if no_team:
            config.search_team.enabled = False
        if team_size:
            config.search_team.team_size = team_size

        # Handle provider selection
        if tavily_only:
            config.search.providers = ["tavily"]
        if claude_only:
            config.search.providers = ["claude"]

        # Create orchestrator
        orchestrator = TeamResearchOrchestrator(
            config=config,
            monitor=research_monitor,
        )

        # Convert depth string to enum
        depth_enum = ResearchDepth(depth)

        # Execute research (async)
        import asyncio
        session = asyncio.run(orchestrator.execute_research(
            query=query,
            depth=depth_enum,
            min_sources=min_sources,
        ))

        # Generate report
        reporter = ReportGenerator(config)
        analysis = session.metadata.get("analysis", {})

        if output_format == "markdown":
            report = reporter.generate_markdown_report(session, analysis)
        else:
            report = reporter.generate_json_report(session, analysis)

        # Output report
        if output:
            # Save to file
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report)
            if not quiet:
                click.echo(f"Report saved to: {output_path}")
        else:
            # Print to stdout
            click.echo(report)

        if monitor and not quiet:
            research_monitor.section("Summary")
            research_monitor.summary(
                total_sources=session.total_sources,
                providers=[s.provider for s in session.searches],
                total_time_ms=int(session.execution_time_seconds * 1000),
            )

    except Exception as e:
        if not quiet:
            click.echo(f"Error: {e}", err=True)
        if monitor and not quiet:
            research_monitor.section("Error")
            research_monitor.log(f"Research failed: {e}")
        raise click.Abort()


@main.group()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Manage configuration settings."""
    pass


@config.command()
@click.argument("key", required=True)
@click.argument("value", required=True)
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
@click.pass_context
def set(ctx: click.Context, key: str, value: str, config_path: str | None) -> None:
    """Set a configuration value.

    KEY is the configuration key in dot notation (e.g., tavily.api_keys).
    VALUE is the value to set.

    Examples:
        cc-deep-research config set tavily.api_keys key1,key2
        cc-deep-research config set search.mode hybrid_parallel
    """
    config_obj = Config()

    if config_path:
        config_path_obj = click.Path().convert(config_path, None, ctx=ctx)
        if config_path_obj.exists():
            config_obj = load_config(Path(config_path_obj))
    else:
        config_obj = load_config()

    # Parse the key path and set the value
    key_parts = key.split(".")
    target = config_obj

    # Navigate to the parent of the final key
    for part in key_parts[:-1]:
        if not hasattr(target, part):
            click.echo(f"Error: Invalid configuration key: {key}", err=True)
            raise click.Abort()
        target = getattr(target, part)

    final_key = key_parts[-1]
    if not hasattr(target, final_key):
        click.echo(f"Error: Invalid configuration key: {key}", err=True)
        raise click.Abort()

    # Handle different value types
    current_value = getattr(target, final_key)
    if isinstance(current_value, list):
        # Handle list values (comma-separated)
        parsed_value = [v.strip() for v in value.split(",") if v.strip()]
    elif isinstance(current_value, bool):
        # Handle boolean values
        parsed_value = value.lower() in ("true", "1", "yes", "on")
    elif isinstance(current_value, int):
        # Handle integer values
        try:
            parsed_value = int(value)
        except ValueError:
            click.echo(
                f"Error: Expected integer value for {key}, got: {value}", err=True
            )
            raise click.Abort()
    else:
        # Handle string values
        parsed_value = value

    # Set the value
    setattr(target, final_key, parsed_value)

    # Save the configuration
    save_path = Path(config_path) if config_path else None
    save_config(config_obj, save_path)

    click.echo(f"Configuration updated: {key} = {parsed_value}")
    if config_path:
        click.echo(f"Saved to: {config_path}")
    else:
        click.echo(f"Saved to: {get_default_config_path()}")


@config.command()
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
@click.pass_context
def show(ctx: click.Context, config_path: str | None) -> None:
    """Show current configuration."""
    if config_path:
        config_obj = load_config(Path(config_path))
    else:
        config_obj = load_config()

    click.echo("Current configuration:")
    click.echo(f"  Search providers: {', '.join(config_obj.search.providers)}")
    click.echo(f"  Search mode: {config_obj.search.mode}")
    click.echo(f"  Search depth: {config_obj.search.depth}")
    click.echo(f"  Tavily API keys: {len(config_obj.tavily.api_keys)} configured")
    click.echo(f"  Output format: {config_obj.output.format}")
    click.echo(f"  Output directory: {config_obj.output.save_dir}")


@config.command()
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
@click.option("--force", is_flag=True, help="Overwrite existing config file")
@click.pass_context
def init(ctx: click.Context, config_path: str | None, force: bool) -> None:
    """Create a default configuration file."""
    from cc_deep_research.config import create_default_config_file

    save_path = Path(config_path) if config_path else None

    if save_path and save_path.exists() and not force:
        click.echo(
            f"Error: Config file already exists at {save_path}. Use --force to overwrite.",
            err=True,
        )
        raise click.Abort()

    created_path = create_default_config_file(save_path)
    click.echo(f"Created default configuration at: {created_path}")


if __name__ == "__main__":
    main()


@main.group()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Manage configuration settings."""
    pass


@config.command()
@click.argument("key", required=True)
@click.argument("value", required=True)
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
@click.pass_context
def set(ctx: click.Context, key: str, value: str, config_path: str | None) -> None:
    """Set a configuration value.

    KEY is the configuration key in dot notation (e.g., tavily.api_keys).
    VALUE is the value to set.

    Examples:
        cc-deep-research config set tavily.api_keys key1,key2
        cc-deep-research config set search.mode hybrid_parallel
    """
    config_obj = Config()

    if config_path:
        config_path_obj = click.Path().convert(config_path, None, ctx=ctx)
        if config_path_obj.exists():
            config_obj = load_config(Path(config_path_obj))
    else:
        config_obj = load_config()

    # Parse the key path and set the value
    key_parts = key.split(".")
    target = config_obj

    # Navigate to the parent of the final key
    for part in key_parts[:-1]:
        if not hasattr(target, part):
            click.echo(f"Error: Invalid configuration key: {key}", err=True)
            raise click.Abort()
        target = getattr(target, part)

    final_key = key_parts[-1]
    if not hasattr(target, final_key):
        click.echo(f"Error: Invalid configuration key: {key}", err=True)
        raise click.Abort()

    # Handle different value types
    current_value = getattr(target, final_key)
    if isinstance(current_value, list):
        # Handle list values (comma-separated)
        parsed_value = [v.strip() for v in value.split(",") if v.strip()]
    elif isinstance(current_value, bool):
        # Handle boolean values
        parsed_value = value.lower() in ("true", "1", "yes", "on")
    elif isinstance(current_value, int):
        # Handle integer values
        try:
            parsed_value = int(value)
        except ValueError:
            click.echo(
                f"Error: Expected integer value for {key}, got: {value}", err=True
            )
            raise click.Abort()
    else:
        # Handle string values
        parsed_value = value

    # Set the value
    setattr(target, final_key, parsed_value)

    # Save the configuration
    save_path = Path(config_path) if config_path else None
    save_config(config_obj, save_path)

    click.echo(f"Configuration updated: {key} = {parsed_value}")
    if config_path:
        click.echo(f"Saved to: {config_path}")
    else:
        click.echo(f"Saved to: {get_default_config_path()}")


@config.command()
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
@click.pass_context
def show(ctx: click.Context, config_path: str | None) -> None:
    """Show current configuration."""
    if config_path:
        config_obj = load_config(Path(config_path))
    else:
        config_obj = load_config()

    click.echo("Current configuration:")
    click.echo(f"  Search providers: {', '.join(config_obj.search.providers)}")
    click.echo(f"  Search mode: {config_obj.search.mode}")
    click.echo(f"  Search depth: {config_obj.search.depth}")
    click.echo(f"  Tavily API keys: {len(config_obj.tavily.api_keys)} configured")
    click.echo(f"  Output format: {config_obj.output.format}")
    click.echo(f"  Output directory: {config_obj.output.save_dir}")


@config.command()
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
@click.option("--force", is_flag=True, help="Overwrite existing config file")
@click.pass_context
def init(ctx: click.Context, config_path: str | None, force: bool) -> None:
    """Create a default configuration file."""
    from cc_deep_research.config import create_default_config_file

    save_path = Path(config_path) if config_path else None

    if save_path and save_path.exists() and not force:
        click.echo(
            f"Error: Config file already exists at {save_path}. Use --force to overwrite.",
            err=True,
        )
        raise click.Abort()

    created_path = create_default_config_file(save_path)
    click.echo(f"Created default configuration at: {created_path}")
