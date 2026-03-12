"""PDF generation for CC Deep Research CLI.

This module provides PDF conversion functionality using WeasyPrint.
Includes graceful degradation when WeasyPrint is not installed.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Set DYLD_LIBRARY_PATH before importing WeasyPrint to help find system libraries
# This is needed on macOS when using Homebrew-installed libraries
homebrew_lib = "/opt/homebrew/lib"
if os.path.exists(homebrew_lib):
    os.environ.setdefault("DYLD_LIBRARY_PATH", homebrew_lib)

from cc_deep_research.markdown_report_formatter import MarkdownReportFormatter

try:
    from weasyprint import CSS, HTML  # type: ignore[import-untyped]

    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False

try:
    import markdown  # type: ignore[import-untyped]

    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False


class PDFGenerationError(Exception):
    """Exception raised when PDF generation fails."""

    pass


class PDFGenerator:
    """Generates PDF reports from Markdown content.

    This class provides:
    - Markdown to PDF conversion using WeasyPrint
    - Custom CSS styling for professional appearance
    - Graceful handling when WeasyPrint is unavailable
    - Metadata embedding (title, author, date)
    """

    def __init__(self) -> None:
        """Initialize the PDF generator.

        Raises:
            PDFGenerationError: If required dependencies are not available.
        """
        if not WEASYPRINT_AVAILABLE:
            raise PDFGenerationError(
                "WeasyPrint is not installed. Please install it: uv add WeasyPrint"
            )
        if not MARKDOWN_AVAILABLE:
            raise PDFGenerationError(
                "markdown package is not installed. Please install it: uv add markdown"
            )

    @staticmethod
    def is_available() -> bool:
        """Check if PDF generation is available.

        Returns:
            True if WeasyPrint and markdown are installed, False otherwise.
        """
        return WEASYPRINT_AVAILABLE and MARKDOWN_AVAILABLE

    def generate_pdf(
        self,
        markdown_content: str,
        output_path: Path,
        title: str = "Research Report",  # noqa: ARG002
    ) -> Path:
        """Generate a PDF from Markdown content.

        Args:
            markdown_content: Markdown formatted research report.
            output_path: Path where PDF should be saved.
            title: Document title for PDF metadata.

        Returns:
            Path to the generated PDF file.

        Raises:
            PDFGenerationError: If PDF generation fails.
        """
        try:
            # Convert Markdown to HTML with extensions
            html_content = self._convert_to_html(markdown_content)

            # Get CSS styles
            css = CSS(string=self._get_css_styles())

            # Ensure output directory exists
            output_path = output_path.with_suffix(".pdf")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate PDF
            HTML(string=html_content).write_pdf(
                output_path,
                stylesheets=[css],
                presentational_hints=True,
            )

            return output_path

        except Exception as e:
            raise PDFGenerationError(f"Failed to generate PDF: {e}") from e

    def _convert_to_html(self, markdown_content: str) -> str:
        """Convert Markdown to HTML with proper extensions.

        Args:
            markdown_content: Markdown formatted text.

        Returns:
            HTML string.
        """
        extensions = [
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.codehilite",
            "markdown.extensions.toc",
            "markdown.extensions.nl2br",
        ]

        try:
            html = markdown.markdown(markdown_content, extensions=extensions)
            # Wrap sections in semantic divs
            wrapped_html = self._wrap_sections_in_html(html)
            return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Research Report</title>
</head>
<body>
    {wrapped_html}
</body>
</html>
            """
        except Exception as e:
            raise PDFGenerationError(f"Failed to convert Markdown to HTML: {e}") from e

    def _wrap_sections_in_html(self, html_content: str) -> str:
        """Wrap each major section in semantic HTML divs.

        This enables section-specific CSS styling and helps de-emphasize
        appendix sections like Sources and Research Metadata.

        Args:
            html_content: Raw HTML from markdown conversion.

        Returns:
            HTML with sections wrapped in semantic divs.
        """
        # Mapping of section heading text to CSS class
        section_classes = {
            "Executive Summary": "section-executive-summary",
            "Methodology": "section-methodology",
            "Key Findings": "section-key-findings",
            "Detailed Analysis": "section-detailed-analysis",
            "Evidence Quality Analysis": "section-evidence-quality",
            "Cross-Reference Analysis": "section-cross-reference",
            "Safety and Contraindications": "section-safety",
            "Research Gaps and Limitations": "section-research-gaps",
            "Sources": "section-sources",
            "Research Metadata": "section-metadata",
        }

        # Wrap title block (h1 at start of document)
        # Account for id attributes that markdown extension may add
        html_content = re.sub(
            r'(<h1[^>]*>)([^<]*)(</h1>)',
            r'<div class="report-section section-title-block">\1\2\3</div>',
            html_content,
            count=1,
        )

        # Wrap each h2 section with its content
        def wrap_h2_section(match):
            heading_open = match.group(1)  # <h2 id="...">
            section_name = match.group(2).strip()  # Executive Summary
            heading_close = match.group(3)  # </h2>
            content = match.group(4)  # Content until next h2

            # Get section class, fall back to generic
            section_class = section_classes.get(section_name, "section-generic")

            return (
                f'<div class="report-section {section_class}">'
                f'{heading_open}{section_name}{heading_close}{content}'
                f'</div>'
            )

        # Pattern: match h2 heading (with possible id attr) and all content until next h2 or end
        html_content = re.sub(
            r'(<h2[^>]*>)([^<]+)(</h2>)(.*?)(?=<h2[^>]*>|$)',
            wrap_h2_section,
            html_content,
            flags=re.DOTALL,
        )

        return html_content

    @staticmethod
    def _get_css_styles() -> str:
        """Return professional CSS for PDF styling.

        Returns:
            CSS stylesheet string.
        """
        return """
        @page {
            size: A4;
            margin: 2.5cm;
            @top-center {
                content: "CC Deep Research Report";
                font-size: 10pt;
                color: #666;
            }
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 10pt;
                color: #666;
            }
        }

        body {
            font-family: Georgia, 'Times New Roman', serif;
            font-size: 11pt;
            line-height: 1.7;
            color: #333;
            max-width: 100%;
        }

        /* Long-form reading sections - serif font for better readability */
        .section-executive-summary,
        .section-key-findings,
        .section-detailed-analysis,
        .section-evidence-quality,
        .section-cross-reference,
        .section-safety,
        .section-research-gaps {
            font-family: Georgia, 'Times New Roman', serif;
            font-size: 11pt;
            line-height: 1.7;
        }

        /* Methodology section - utility section, sans-serif */
        .section-methodology {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.5;
            color: #555;
        }

        /* Appendix sections - compact, lighter sans-serif */
        .section-sources,
        .section-metadata {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 9pt;
            line-height: 1.3;
            color: #777;
        }

        /* Appendix headings */
        .section-sources h3,
        .section-metadata h2 {
            font-size: 11pt;
            color: #555;
            margin-top: 1.5em;
            margin-bottom: 0.8em;
        }

        /* Appendix links - quieter color */
        .section-sources a {
            color: #555;
            text-decoration: none;
        }

        /* Compact source list items */
        .section-sources ul,
        .section-sources li {
            margin-bottom: 0.3em;
        }

        /* Compact metadata list */
        .section-metadata ul {
            margin-left: 1.5em;
            margin-bottom: 0.5em;
        }

        h1 {
            color: #2c3e50;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 24pt;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
            margin-bottom: 20px;
        }

        h2 {
            color: #34495e;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 18pt;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
            margin-top: 25px;
            margin-bottom: 15px;
        }

        h3 {
            color: #34495e;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 14pt;
            margin-top: 20px;
            margin-bottom: 10px;
        }

        p {
            margin-bottom: 12px;
            text-align: left;
        }

        /* Improved paragraph spacing for long-form sections */
        .section-executive-summary p,
        .section-detailed-analysis p {
            margin-bottom: 1.2em;
        }

        a {
            color: #3498db;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        strong, b {
            color: #2c3e50;
        }

        em, i {
            color: #555;
        }

        ul, ol {
            margin-left: 2em;
            margin-bottom: 1.5em;
        }

        li {
            margin-bottom: 0.8em;
        }

        code {
            background-color: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Courier New", Courier, monospace;
            font-size: 10pt;
            color: #e74c3c;
        }

        pre {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 15px;
            margin: 15px 0;
            overflow-x: auto;
        }

        pre code {
            background-color: transparent;
            padding: 0;
            border-radius: 0;
            color: #333;
        }

        blockquote {
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin: 15px 0;
            color: #666;
            background-color: #f8f9fa;
            padding-top: 10px;
            padding-bottom: 10px;
        }

        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }

        th, td {
            border: 1px solid #dee2e6;
            padding: 10px;
            text-align: left;
        }

        th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #2c3e50;
        }

        tr:nth-child(even) {
            background-color: #f8f9fa;
        }

        hr {
            border: none;
            border-top: 2px solid #dee2e6;
            margin: 20px 0;
        }

        /* Page-break protection for headings */
        h1, h2, h3 {
            page-break-after: avoid;
            page-break-inside: avoid;
            break-after: avoid;
            break-inside: avoid;
        }

        /* Orphan control for paragraphs */
        p {
            orphans: 2;
            widows: 2;
        }

        /* Page-break before full source catalog */
        .section-sources h3:first-of-type {
            page-break-before: always;
            break-before: always;
        }
        """


def generate_pdf_report_from_markdown_file(
    input_path: Path,
    output_path: Path | None = None,
    title: str | None = None,
) -> Path:
    """Format a markdown file as a report and write it as a PDF."""
    markdown_content = input_path.read_text(encoding="utf-8")
    if not markdown_content.strip():
        raise PDFGenerationError(f"Markdown input file is empty: {input_path}")

    formatter = MarkdownReportFormatter()
    formatted_report = formatter.format_report(markdown_content, source_path=input_path, title=title)
    pdf_path = output_path or input_path.with_suffix(".pdf")

    pdf_generator = PDFGenerator()
    return pdf_generator.generate_pdf(
        formatted_report.markdown,
        pdf_path,
        title=formatted_report.title,
    )


__all__ = [
    "PDFGenerator",
    "PDFGenerationError",
    "generate_pdf_report_from_markdown_file",
]
