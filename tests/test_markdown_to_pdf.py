"""Tests for markdown-to-pdf report formatting and CLI export."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from cc_deep_research.cli import main
from cc_deep_research.html_report_renderer import (
    HTMLReportGenerationError,
    HTMLReportRenderer,
    generate_html_report_from_markdown_file,
)
from cc_deep_research.markdown_report_formatter import MarkdownReportFormatter
from cc_deep_research.pdf_generator import (
    PDFGenerationError,
    PDFGenerator,
    generate_pdf_report_from_markdown_file,
)


class TestMarkdownReportFormatter:
    """Validate report normalization for arbitrary markdown files."""

    def test_format_report_applies_predefined_structure(self, tmp_path: Path) -> None:
        formatter = MarkdownReportFormatter()
        source_path = tmp_path / "market-notes.md"

        markdown = """# Market Notes

This memo summarizes the quarter and captures the main operating changes.
Revenue expanded because enterprise renewals landed ahead of plan.

- Revenue grew 22% year over year after enterprise renewals closed.
- Gross margin narrowed because hosting costs rose during migration.

## Analysis

The migration increased operating complexity while keeping customer churn flat.
See the [board deck](https://example.com/board-deck) and https://example.com/ops-update for detail.
"""

        formatted_report = formatter.format_report(markdown, source_path=source_path)

        assert formatted_report.title == "Market Notes"
        for section in (
            "## Executive Summary",
            "## Key Findings",
            "## Detailed Analysis",
            "## Sources",
            "## Safety",
            "## Research Metadata",
        ):
            assert section in formatted_report.markdown

        assert "- Revenue grew 22% year over year after enterprise renewals closed." in formatted_report.markdown
        assert "https://example.com/board-deck" in formatted_report.markdown
        assert "No explicit safety, risk, warning, or contraindication content was detected" in (
            formatted_report.markdown
        )

    def test_format_report_reuses_existing_sections_without_duplication(self, tmp_path: Path) -> None:
        formatter = MarkdownReportFormatter()
        source_path = tmp_path / "existing-report.md"

        markdown = """# Existing Report

## Executive Summary

Existing summary.

## Key Findings

- Existing finding.

## Analysis

Existing analysis body.

## Sources

1. [Example](https://example.com/report)

## Safety

Existing safety note.
"""

        formatted_report = formatter.format_report(markdown, source_path=source_path)

        assert formatted_report.markdown.count("## Executive Summary") == 1
        assert formatted_report.markdown.count("## Key Findings") == 1
        assert formatted_report.markdown.count("## Sources") == 1
        assert "Existing summary." in formatted_report.markdown
        assert "Existing finding." in formatted_report.markdown
        assert "Existing analysis body." in formatted_report.markdown
        assert "Existing safety note." in formatted_report.markdown


def test_generate_pdf_report_from_markdown_file_rejects_empty_input(tmp_path: Path) -> None:
    input_path = tmp_path / "empty.md"
    input_path.write_text("   \n", encoding="utf-8")

    with pytest.raises(PDFGenerationError, match="Markdown input file is empty"):
        generate_pdf_report_from_markdown_file(input_path=input_path)


def test_generate_html_report_from_markdown_file_rejects_empty_input(tmp_path: Path) -> None:
    input_path = tmp_path / "empty.md"
    input_path.write_text("   \n", encoding="utf-8")

    with pytest.raises(HTMLReportGenerationError, match="Markdown input file is empty"):
        generate_html_report_from_markdown_file(input_path=input_path)


def test_generate_pdf_report_from_markdown_file_uses_html_renderer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "notes.md"
    output_path = tmp_path / "notes-report.pdf"
    input_path.write_text("# Notes\n\nHello report.\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_render_document(
        _self: HTMLReportRenderer,
        markdown_content: str,
        title: str | None = None,
    ) -> str:
        captured["markdown_content"] = markdown_content
        captured["title"] = title
        return "<html><body>report</body></html>"

    def fake_generate_pdf_from_html(
        _self: PDFGenerator,
        html_content: str,
        output_path: Path,
    ) -> Path:
        captured["html_content"] = html_content
        captured["output_path"] = output_path
        output_path.write_bytes(b"%PDF-1.4\n")
        return output_path

    monkeypatch.setattr(
        "cc_deep_research.html_report_renderer.HTMLReportRenderer.render_document",
        fake_render_document,
    )
    monkeypatch.setattr(
        "cc_deep_research.pdf_generator.WEASYPRINT_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        "cc_deep_research.pdf_generator.PDFGenerator.generate_pdf_from_html",
        fake_generate_pdf_from_html,
    )

    pdf_path = generate_pdf_report_from_markdown_file(
        input_path=input_path,
        output_path=output_path,
    )

    assert pdf_path == output_path
    assert captured["html_content"] == "<html><body>report</body></html>"
    assert captured["output_path"] == output_path
    assert captured["title"] == "Notes"
    assert "## Executive Summary" in str(captured["markdown_content"])


def test_markdown_to_pdf_command_generates_pdf_via_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "notes.md"
    output_path = tmp_path / "notes-report.pdf"
    input_path.write_text("# Notes\n\nHello report.\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_generate_pdf_report_from_markdown_file(
        input_path: Path,
        output_path: Path | None = None,
        title: str | None = None,
    ) -> Path:
        captured["input_path"] = input_path
        captured["output_path"] = output_path
        captured["title"] = title
        pdf_path = output_path or input_path.with_suffix(".pdf")
        pdf_path.write_bytes(b"%PDF-1.4\n")
        return pdf_path

    monkeypatch.setattr(
        "cc_deep_research.pdf_generator.generate_pdf_report_from_markdown_file",
        fake_generate_pdf_report_from_markdown_file,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "markdown-to-pdf",
            str(input_path),
            "-o",
            str(output_path),
            "--title",
            "Custom Report",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert captured == {
        "input_path": input_path,
        "output_path": output_path,
        "title": "Custom Report",
    }


def test_markdown_to_html_command_generates_html_via_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "notes.md"
    output_path = tmp_path / "notes-report.html"
    input_path.write_text("# Notes\n\nHello report.\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_generate_html_report_from_markdown_file(
        input_path: Path,
        output_path: Path | None = None,
        title: str | None = None,
    ) -> Path:
        captured["input_path"] = input_path
        captured["output_path"] = output_path
        captured["title"] = title
        html_path = output_path or input_path.with_suffix(".html")
        html_path.write_text("<html></html>", encoding="utf-8")
        return html_path

    monkeypatch.setattr(
        "cc_deep_research.html_report_renderer.generate_html_report_from_markdown_file",
        fake_generate_html_report_from_markdown_file,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "markdown-to-html",
            str(input_path),
            "-o",
            str(output_path),
            "--title",
            "Custom Report",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert captured == {
        "input_path": input_path,
        "output_path": output_path,
        "title": "Custom Report",
    }


class TestHTMLReportRenderer:
    """Test that HTML export includes semantic wrappers and shared styles."""

    def test_html_has_section_wrappers(self) -> None:
        """Test that major sections are wrapped in semantic divs."""
        renderer = HTMLReportRenderer()

        markdown = """# Test Report
## Executive Summary
Test summary content.
## Safety
Safety note.
## Sources
1. [Source](https://example.com)
## Research Metadata
- Query: test
"""

        html = renderer.render_document(markdown)

        # Check for common class (report-section appears in class attribute)
        assert 'report-section' in html

        # Check for section-specific classes
        assert 'section-executive-summary' in html
        assert 'section-safety' in html
        assert 'section-sources' in html
        assert 'section-metadata' in html

        # Check for title block wrapper
        assert 'section-title-block' in html
        assert "<style>" in html

    def test_css_includes_section_selectors(self) -> None:
        """Test that section-specific CSS selectors are present."""
        css = HTMLReportRenderer.get_stylesheet()

        # Check for section classes
        assert '.section-executive-summary' in css
        assert '.section-key-findings' in css
        assert '.section-detailed-analysis' in css
        assert '.section-sources' in css
        assert '.section-metadata' in css

        # Check for typography differences
        assert 'Georgia' in css or 'serif' in css
        assert '-apple-system' in css

    def test_css_includes_appendix_de_emphasis(self) -> None:
        """Test that appendix sections have de-emphasis styling."""
        css = HTMLReportRenderer.get_stylesheet()

        # Check for appendix-specific styles
        assert '.section-sources' in css
        assert '.section-metadata' in css
        assert 'color: #777' in css  # Lighter color for appendix
        assert 'line-height: 1.3' in css  # Tighter line height for appendix

        # Check for page-break rules
        assert 'page-break-before: always' in css
        assert 'break-before: always' in css

    def test_css_includes_page_break_protection(self) -> None:
        """Test that headings have page-break protection."""
        css = HTMLReportRenderer.get_stylesheet()

        # Check for page-break protection on headings
        assert 'h1, h2, h3' in css
        assert 'page-break-after: avoid' in css
        assert 'page-break-inside: avoid' in css
        assert 'break-after: avoid' in css
        assert 'break-inside: avoid' in css

        # Check for orphan/widow control
        assert 'orphans: 2' in css
        assert 'widows: 2' in css

    def test_css_removes_justify_from_body(self) -> None:
        """Test that paragraphs are left-aligned instead of justified."""
        css = HTMLReportRenderer.get_stylesheet()

        # Find the body p rule
        assert 'text-align: left' in css
        # Should NOT have justify in the main p rule
        # (The old CSS had text-align: justify, new CSS has left)
        assert css.count('text-align: justify') == 0
