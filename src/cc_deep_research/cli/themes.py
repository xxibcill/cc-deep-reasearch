"""Theme management CLI commands."""

from __future__ import annotations

import click

from cc_deep_research.themes import (
    ThemeDetector,
    list_presets,
)


def register_themes_commands(cli: click.Group) -> None:
    """Register theme-related CLI commands."""

    @cli.command()
    def list_themes() -> None:
        """List all available research themes."""
        presets = list_presets()

        click.echo("Available research themes:\n")
        for preset in presets:
            click.echo(f"  {preset['theme']}")
            click.echo(f"    Name: {preset['display_name']}")
            click.echo(f"    Description: {preset['description']}")
            click.echo()

    @cli.command()
    @click.argument("query", required=True)
    def detect_theme(query: str) -> None:
        """Detect the research theme for a query."""
        detector = ThemeDetector()
        result = detector.detect(query)

        click.echo(f"Query: {query}")
        click.echo(f"Detected theme: {result.detected_theme.value}")
        click.echo(f"Confidence: {result.confidence:.2f}")

        if result.matched_patterns:
            click.echo(f"Matched patterns: {', '.join(result.matched_patterns[:5])}")

        if result.all_scores:
            click.echo("\nAll theme scores:")
            sorted_scores = sorted(result.all_scores.items(), key=lambda x: x[1], reverse=True)
            for theme, score in sorted_scores[:5]:
                click.echo(f"  {theme}: {score:.2f}")


__all__ = ["register_themes_commands"]
