"""CLI commands for Anthropic API usage tracking."""

from __future__ import annotations

import json

import click

from cc_deep_research.llm.usage_tracker import (
    DEFAULT_USAGE_LOG_PATH,
    get_lifetime_summary,
)


@click.group()
def anthropic() -> None:
    """Anthropic API commands."""
    pass


@anthropic.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--total-only", is_flag=True, help="Show only total counts")
def usage(as_json: bool, total_only: bool) -> None:
    """Show Anthropic API usage statistics.

    Reads from data/token_usage.jsonl and displays lifetime usage summary.
    """
    summary = get_lifetime_summary()

    if as_json:
        data = {
            "log_file": str(DEFAULT_USAGE_LOG_PATH),
            "totals": {
                "requests": summary.total_requests,
                "input_tokens": summary.total_input_tokens,
                "output_tokens": summary.total_output_tokens,
                "total_tokens": summary.total_tokens,
                "cache_creation_tokens": summary.total_cache_creation_tokens,
                "cache_read_tokens": summary.total_cache_read_tokens,
            },
        }
        if not total_only:
            data["averages"] = {
                "input_tokens": summary.average_input_tokens,
                "output_tokens": summary.average_output_tokens,
                "latency_ms": summary.average_latency_ms,
            }
        click.echo(json.dumps(data, indent=2))
        return

    # Human-readable output
    click.echo("=== Anthropic API Lifetime Usage Summary ===")
    click.echo(f"Log file: {DEFAULT_USAGE_LOG_PATH}")
    click.echo()

    click.echo("Totals:")
    click.echo(f"  Requests: {summary.total_requests}")
    click.echo(f"  Input tokens: {summary.total_input_tokens}")
    click.echo(f"  Output tokens: {summary.total_output_tokens}")
    click.echo(f"  Total tokens: {summary.total_tokens}")
    click.echo(f"  Cache creation tokens: {summary.total_cache_creation_tokens}")
    click.echo(f"  Cache read tokens: {summary.total_cache_read_tokens}")

    if not total_only:
        click.echo()
        click.echo("Averages per request:")
        click.echo(f"  Input tokens: {summary.average_input_tokens:.2f}")
        click.echo(f"  Output tokens: {summary.average_output_tokens:.2f}")
        click.echo(f"  Latency: {summary.average_latency_ms:.2f}ms")


def register_anthropic_commands(cli: click.Group) -> None:
    """Register Anthropic CLI commands with the main CLI group.

    Args:
        cli: The main CLI group to register commands with.
    """
    cli.add_command(anthropic)


__all__ = ["anthropic", "usage", "register_anthropic_commands"]
