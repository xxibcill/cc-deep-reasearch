"""CLI entry point for CC Deep Research."""

import click

from cc_deep_research import __version__


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
@click.option("--progress", is_flag=True, default=True, help="Show progress indicators")
@click.option("--quiet", is_flag=True, help="Suppress output")
@click.option("--verbose", is_flag=True, help="Show detailed output")
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
    progress: bool,
    quiet: bool,
    verbose: bool,
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
    ctx.obj["progress"] = progress
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose

    if verbose:
        click.echo(f"Research query: {query}")
        click.echo(f"Depth: {depth}")
        click.echo(f"Output format: {output_format}")

    # TODO: Implement actual research logic
    click.echo(f"Researching: {query}")
    click.echo("(Research functionality will be implemented in subsequent tasks)")


if __name__ == "__main__":
    main()
