"""HTML rendering for report export workflows."""

from __future__ import annotations

import html
import re
from pathlib import Path

from cc_deep_research.markdown_report_formatter import MarkdownReportFormatter

try:
    import markdown  # type: ignore[import-untyped]

    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False


class HTMLReportGenerationError(Exception):
    """Exception raised when HTML report generation fails."""


class HTMLReportRenderer:
    """Render canonical markdown reports as styled HTML documents."""

    _MARKDOWN_EXTENSIONS = [
        "markdown.extensions.tables",
        "markdown.extensions.fenced_code",
        "markdown.extensions.codehilite",
        "markdown.extensions.toc",
        "markdown.extensions.nl2br",
    ]

    _SECTION_CLASSES: dict[str, str] = {
        "Executive Summary": "section-executive-summary",
        "Methodology": "section-methodology",
        "Key Findings": "section-key-findings",
        "Detailed Analysis": "section-detailed-analysis",
        "Evidence Quality Analysis": "section-evidence-quality",
        "Cross-Reference Analysis": "section-cross-reference",
        "Safety": "section-safety",
        "Safety and Contraindications": "section-safety",
        "Research Gaps and Limitations": "section-research-gaps",
        "Sources": "section-sources",
        "Research Metadata": "section-metadata",
    }

    def __init__(self) -> None:
        """Initialize the HTML renderer."""
        if not MARKDOWN_AVAILABLE:
            raise HTMLReportGenerationError(
                "markdown package is not installed. Please install it: uv add markdown"
            )

    @staticmethod
    def is_available() -> bool:
        """Check whether markdown-to-HTML rendering is available."""
        return MARKDOWN_AVAILABLE

    def render_document(
        self,
        markdown_content: str,
        title: str | None = None,
    ) -> str:
        """Render a full HTML document from report markdown."""
        try:
            document_title = title or self._extract_title(markdown_content)
            body_html = markdown.markdown(
                markdown_content,
                extensions=self._MARKDOWN_EXTENSIONS,
            )
            wrapped_html = self._wrap_sections_in_html(body_html)
            return self._build_html_document(
                title=document_title,
                body_html=wrapped_html,
                stylesheet=self.get_stylesheet(),
            )
        except Exception as error:
            raise HTMLReportGenerationError(
                f"Failed to convert Markdown to HTML: {error}"
            ) from error

    def write_html(
        self,
        markdown_content: str,
        output_path: Path,
        title: str | None = None,
    ) -> Path:
        """Render markdown and write the result to an HTML file."""
        html_content = self.render_document(markdown_content, title=title)
        html_path = output_path.with_suffix(".html")
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_content, encoding="utf-8")
        return html_path

    def _wrap_sections_in_html(self, html_content: str) -> str:
        """Wrap each major section in semantic HTML containers."""
        html_content = re.sub(
            r'(<h1[^>]*>)([^<]*)(</h1>)',
            r'<div class="report-section section-title-block">\1\2\3</div>',
            html_content,
            count=1,
        )

        def wrap_h2_section(match: re.Match[str]) -> str:
            heading_open = match.group(1)
            section_name = match.group(2).strip()
            heading_close = match.group(3)
            content = match.group(4)
            section_class = self._SECTION_CLASSES.get(section_name, "section-generic")

            return (
                f'<div class="report-section {section_class}">'
                f"{heading_open}{section_name}{heading_close}{content}"
                "</div>"
            )

        return re.sub(
            r'(<h2[^>]*>)([^<]+)(</h2>)(.*?)(?=<h2[^>]*>|$)',
            wrap_h2_section,
            html_content,
            flags=re.DOTALL,
        )

    @staticmethod
    def _extract_title(markdown_content: str) -> str:
        """Derive a document title from the first markdown heading."""
        for line in markdown_content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                if title:
                    return title
        return "Research Report"

    @staticmethod
    def _build_html_document(title: str, body_html: str, stylesheet: str) -> str:
        """Assemble a full HTML document with embedded styles."""
        escaped_title = html.escape(title)
        return "\n".join(
            [
                "<!DOCTYPE html>",
                '<html lang="en">',
                "<head>",
                '    <meta charset="UTF-8">',
                f"    <title>{escaped_title}</title>",
                "    <style>",
                stylesheet,
                "    </style>",
                "</head>",
                "<body>",
                f"{body_html}",
                "</body>",
                "</html>",
            ]
        )

    @staticmethod
    def get_stylesheet() -> str:
        """Return the shared stylesheet for HTML and PDF export."""
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

        .section-methodology {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.5;
            color: #555;
        }

        .section-sources,
        .section-metadata {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 9pt;
            line-height: 1.3;
            color: #777;
        }

        .section-sources h3,
        .section-metadata h2 {
            font-size: 11pt;
            color: #555;
            margin-top: 1.5em;
            margin-bottom: 0.8em;
        }

        .section-sources a {
            color: #555;
            text-decoration: none;
        }

        .section-sources ul,
        .section-sources li {
            margin-bottom: 0.3em;
        }

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

        h1, h2, h3 {
            page-break-after: avoid;
            page-break-inside: avoid;
            break-after: avoid;
            break-inside: avoid;
        }

        p {
            orphans: 2;
            widows: 2;
        }

        .section-sources h3:first-of-type {
            page-break-before: always;
            break-before: always;
        }
        """


def generate_html_report_from_markdown_file(
    input_path: Path,
    output_path: Path | None = None,
    title: str | None = None,
) -> Path:
    """Format a markdown file as a report and write it as HTML."""
    markdown_content = input_path.read_text(encoding="utf-8")
    if not markdown_content.strip():
        raise HTMLReportGenerationError(f"Markdown input file is empty: {input_path}")

    formatter = MarkdownReportFormatter()
    formatted_report = formatter.format_report(markdown_content, source_path=input_path, title=title)
    html_path = output_path or input_path.with_suffix(".html")

    renderer = HTMLReportRenderer()
    return renderer.write_html(
        formatted_report.markdown,
        html_path,
        title=formatted_report.title,
    )


__all__ = [
    "HTMLReportRenderer",
    "HTMLReportGenerationError",
    "generate_html_report_from_markdown_file",
]
