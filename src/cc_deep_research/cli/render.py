"""Render command registration."""

from __future__ import annotations

from pathlib import Path

import click

from cc_deep_research.tui import TerminalUI


def register_render_commands(cli: click.Group) -> None:
    """Register markdown render/export commands."""

    @cli.command("markdown-to-pdf")
    @click.argument(
        "input_path",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
    )
    @click.option(
        "-o",
        "--output",
        type=click.Path(dir_okay=False, path_type=Path),
        default=None,
        help="Output PDF path (defaults to the input filename with a .pdf extension).",
    )
    @click.option("--title", default=None, help="Optional report title override.")
    def markdown_to_pdf(input_path: Path, output: Path | None, title: str | None) -> None:
        """Convert a markdown file into a formatted PDF report."""
        from cc_deep_research.pdf_generator import (
            PDFGenerationError,
            generate_pdf_report_from_markdown_file,
        )

        try:
            pdf_path = generate_pdf_report_from_markdown_file(
                input_path=input_path,
                output_path=output,
                title=title,
            )
        except PDFGenerationError as error:
            raise click.ClickException(str(error)) from error
        except OSError as error:
            raise click.ClickException(f"Failed to read markdown input: {error}") from error

        TerminalUI(enabled=True).show_report_saved(pdf_path)

    @cli.command("markdown-to-html")
    @click.argument(
        "input_path",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
    )
    @click.option(
        "-o",
        "--output",
        type=click.Path(dir_okay=False, path_type=Path),
        default=None,
        help="Output HTML path (defaults to the input filename with a .html extension).",
    )
    @click.option("--title", default=None, help="Optional report title override.")
    def markdown_to_html(input_path: Path, output: Path | None, title: str | None) -> None:
        """Convert a markdown file into a formatted HTML report."""
        from cc_deep_research.html_report_renderer import (
            HTMLReportGenerationError,
            generate_html_report_from_markdown_file,
        )

        try:
            html_path = generate_html_report_from_markdown_file(
                input_path=input_path,
                output_path=output,
                title=title,
            )
        except HTMLReportGenerationError as error:
            raise click.ClickException(str(error)) from error
        except OSError as error:
            raise click.ClickException(f"Failed to read markdown input: {error}") from error

        TerminalUI(enabled=True).show_report_saved(html_path)


__all__ = ["register_render_commands"]
