"""PDF generation for CC Deep Research CLI.

This module provides PDF conversion functionality using WeasyPrint.
Includes graceful degradation when WeasyPrint is not installed.
"""

from __future__ import annotations

from pathlib import Path

try:
    from weasyprint import CSS, HTML  # type: ignore[import-untyped]

    WEASYPRINT_AVAILABLE = True
except ImportError:
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
                "WeasyPrint is not installed. Please install it: pip install WeasyPrint"
            )
        if not MARKDOWN_AVAILABLE:
            raise PDFGenerationError(
                "markdown package is not installed. Please install it: pip install markdown"
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
            return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Research Report</title>
</head>
<body>
    {html}
</body>
</html>
            """
        except Exception as e:
            raise PDFGenerationError(f"Failed to convert Markdown to HTML: {e}") from e

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
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            max-width: 100%;
        }

        h1 {
            color: #2c3e50;
            font-size: 24pt;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
            margin-bottom: 20px;
        }

        h2 {
            color: #34495e;
            font-size: 18pt;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
            margin-top: 25px;
            margin-bottom: 15px;
        }

        h3 {
            color: #34495e;
            font-size: 14pt;
            margin-top: 20px;
            margin-bottom: 10px;
        }

        p {
            margin-bottom: 12px;
            text-align: justify;
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
            margin-bottom: 15px;
        }

        li {
            margin-bottom: 5px;
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
        """


__all__ = [
    "PDFGenerator",
    "PDFGenerationError",
]
