"""Shared research-run output materialization helpers."""

from __future__ import annotations

from pathlib import Path

from cc_deep_research.config import Config
from cc_deep_research.pdf_generator import PDFGenerationError, PDFGenerator
from cc_deep_research.reporting import ReportGenerator
from cc_deep_research.research_runs.models import (
    ResearchArtifactKind,
    ResearchOutputFormat,
    ResearchRunArtifact,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
)
from cc_deep_research.session_store import SessionStore


def materialize_research_run_output(
    *,
    session,
    config: Config,
    request: ResearchRunRequest,
    session_store: SessionStore | None = None,
    reporter: ReportGenerator | None = None,
    pdf_generator: PDFGenerator | None = None,
) -> ResearchRunResult:
    """Persist a session and materialize report artifacts for the caller."""
    store = session_store or SessionStore()
    report_generator = reporter or ReportGenerator(config)
    artifacts: list[ResearchRunArtifact] = []
    warnings: list[str] = []

    session_path = store.save_session(session)
    artifacts.append(
        ResearchRunArtifact(
            kind=ResearchArtifactKind.SESSION,
            path=session_path,
            format="json",
            media_type="application/json",
        )
    )

    analysis = session.metadata.get("analysis", {})
    markdown_report: str | None = None
    if request.output_format == ResearchOutputFormat.JSON:
        report_content = report_generator.generate_json_report(session, analysis)
    else:
        markdown_report = report_generator.generate_markdown_report(session, analysis)
        if request.output_format == ResearchOutputFormat.HTML:
            report_content = report_generator.render_html_report(markdown_report)
        else:
            report_content = markdown_report

    store.save_report(session.session_id, request.output_format, report_content)
    if markdown_report is not None and request.output_format != ResearchOutputFormat.MARKDOWN:
        store.save_report(session.session_id, ResearchOutputFormat.MARKDOWN, markdown_report)

    report_path = request.output_path
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_content, encoding="utf-8")
        artifacts.append(
            ResearchRunArtifact(
                kind=ResearchArtifactKind.REPORT,
                path=report_path,
                format=request.output_format.value,
                media_type=_media_type_for_format(request.output_format),
            )
        )

    if request.pdf_enabled:
        try:
            generator = pdf_generator or PDFGenerator()
            if markdown_report is None:
                markdown_report = report_generator.generate_markdown_report(session, analysis)
            html_report = report_generator.render_html_report(markdown_report)
            pdf_path = report_path.with_suffix(".pdf") if report_path else Path("research_report.pdf")
            generator.generate_pdf_from_html(html_report, pdf_path)
            artifacts.append(
                ResearchRunArtifact(
                    kind=ResearchArtifactKind.PDF,
                    path=pdf_path,
                    format="pdf",
                    media_type="application/pdf",
                )
            )
        except PDFGenerationError as error:
            warnings.append(str(error))
        except Exception as error:  # pragma: no cover - defensive fallback
            warnings.append(f"Failed to generate PDF: {error}")

    return ResearchRunResult(
        session=session,
        report=ResearchRunReport(
            format=request.output_format,
            content=report_content,
            path=report_path,
            media_type=_media_type_for_format(request.output_format),
        ),
        artifacts=artifacts,
        warnings=warnings,
    )


def _media_type_for_format(output_format: ResearchOutputFormat) -> str:
    """Map a report format to the response media type."""
    if output_format == ResearchOutputFormat.JSON:
        return "application/json"
    if output_format == ResearchOutputFormat.HTML:
        return "text/html"
    return "text/markdown"
