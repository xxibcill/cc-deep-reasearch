"""PDF generation for CC Deep Research CLI."""

from __future__ import annotations

import os
from pathlib import Path

from cc_deep_research.html_report_renderer import HTMLReportGenerationError, HTMLReportRenderer
from cc_deep_research.markdown_report_formatter import MarkdownReportFormatter

# Set DYLD_LIBRARY_PATH before importing WeasyPrint to help find system libraries
# This is needed on macOS when using Homebrew-installed libraries
homebrew_lib = "/opt/homebrew/lib"
if os.path.exists(homebrew_lib):
    os.environ.setdefault("DYLD_LIBRARY_PATH", homebrew_lib)

try:
    from weasyprint import HTML  # type: ignore[import-untyped]

    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False


class PDFGenerationError(Exception):
    """Exception raised when PDF generation fails."""


class PDFGenerator:
    """Generate PDF reports from rendered HTML documents."""

    def __init__(self) -> None:
        """Initialize the PDF generator."""
        if not WEASYPRINT_AVAILABLE:
            raise PDFGenerationError(
                "WeasyPrint is not installed. Please install it: uv add WeasyPrint"
            )

    @staticmethod
    def is_available() -> bool:
        """Check if HTML-to-PDF generation is available."""
        return WEASYPRINT_AVAILABLE

    def generate_pdf_from_html(
        self,
        html_content: str,
        output_path: Path,
    ) -> Path:
        """Write a PDF file from a rendered HTML document."""
        try:
            output_path = output_path.with_suffix(".pdf")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            HTML(string=html_content).write_pdf(
                output_path,
                presentational_hints=True,
            )
            return output_path
        except Exception as error:
            raise PDFGenerationError(f"Failed to generate PDF: {error}") from error

    def generate_pdf(
        self,
        markdown_content: str,
        output_path: Path,
        title: str = "Research Report",
    ) -> Path:
        """Backward-compatible helper that renders markdown before writing PDF."""
        try:
            renderer = HTMLReportRenderer()
            html_content = renderer.render_document(markdown_content, title=title)
            return self.generate_pdf_from_html(html_content, output_path)
        except HTMLReportGenerationError as error:
            raise PDFGenerationError(str(error)) from error


def generate_pdf_report_from_markdown_file(
    input_path: Path,
    output_path: Path | None = None,
    title: str | None = None,
) -> Path:
    """Format a markdown file as a report and write it as a PDF."""
    try:
        markdown_content = input_path.read_text(encoding="utf-8")
        if not markdown_content.strip():
            raise PDFGenerationError(f"Markdown input file is empty: {input_path}")

        formatter = MarkdownReportFormatter()
        formatted_report = formatter.format_report(
            markdown_content,
            source_path=input_path,
            title=title,
        )
        renderer = HTMLReportRenderer()
        html_content = renderer.render_document(
            formatted_report.markdown,
            title=formatted_report.title,
        )
        pdf_path = output_path or input_path.with_suffix(".pdf")

        pdf_generator = PDFGenerator()
        return pdf_generator.generate_pdf_from_html(html_content, pdf_path)
    except HTMLReportGenerationError as error:
        raise PDFGenerationError(str(error)) from error


__all__ = [
    "PDFGenerator",
    "PDFGenerationError",
    "generate_pdf_report_from_markdown_file",
]
