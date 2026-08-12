"""Shared research-run output materialization helpers."""

from __future__ import annotations

import json
import logging
from html import escape
from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.models import ResearchSession
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.pdf_generator import PDFGenerationError, PDFGenerator
from cc_deep_research.persistence import atomic_write_text
from cc_deep_research.reporting import ReportGenerator, record_report_degradation
from cc_deep_research.research_runs.models import (
    ResearchArtifactKind,
    ResearchOutputFormat,
    ResearchRunArtifact,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
)
from cc_deep_research.session_store import SessionStore

# Optional: knowledge vault ingest (non-fatal)
try:
    from cc_deep_research.knowledge.ingest import ingest_session
    _KNOWLEDGE_AVAILABLE = True
except Exception:
    _KNOWLEDGE_AVAILABLE = False

logger = logging.getLogger(__name__)


def materialize_research_run_output(
    *,
    session: ResearchSession,
    config: Config,
    request: ResearchRunRequest,
    monitor: ResearchMonitor | None = None,
    session_store: SessionStore | None = None,
    reporter: ReportGenerator | None = None,
    pdf_generator: PDFGenerator | None = None,
) -> ResearchRunResult:
    """Persist a session and materialize report artifacts for the caller."""
    store = session_store or SessionStore()
    report_generator = reporter or ReportGenerator(config, monitor=monitor)
    artifacts: list[ResearchRunArtifact] = []
    warnings: list[str] = []
    initial_degradation_reasons = set(_degradation_reasons(session))

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
    try:
        if request.output_format == ResearchOutputFormat.JSON:
            report_content = report_generator.generate_json_report(session, analysis)
        else:
            markdown_report = report_generator.generate_markdown_report(session, analysis)
            if request.output_format == ResearchOutputFormat.HTML:
                report_content = report_generator.render_html_report(markdown_report)
            else:
                report_content = markdown_report
    except Exception as error:
        logger.exception(
            "Primary report generation failed for session %s; building recovery report",
            session.session_id,
        )
        warning = (
            f"Report generation failed ({type(error).__name__}); "
            "generated a recovery report from partial session data."
        )
        record_report_degradation(session, warning)
        markdown_report = _build_recovery_markdown(session, analysis)
        report_content = _render_recovery_report(
            request.output_format,
            markdown_report=markdown_report,
            session=session,
            analysis=analysis,
            warning=warning,
        )

    current_degradation_reasons = _degradation_reasons(session)
    warnings.extend(
        reason
        for reason in current_degradation_reasons
        if isinstance(reason, str) and reason not in initial_degradation_reasons
    )

    cached_report_path = store.save_report(
        session.session_id,
        request.output_format,
        report_content,
    )
    if markdown_report is not None and request.output_format != ResearchOutputFormat.MARKDOWN:
        store.save_report(session.session_id, ResearchOutputFormat.MARKDOWN, markdown_report)

    report_path = request.output_path
    artifact_path = cached_report_path
    if report_path is not None:
        try:
            atomic_write_text(report_path, report_content)
        except OSError as error:
            logger.warning(
                "Unable to write requested report path for session %s: %s",
                session.session_id,
                type(error).__name__,
            )
            warnings.append(
                "Failed to write the requested report path; cached report retained "
                f"({type(error).__name__})."
            )
            report_path = None
        else:
            artifact_path = report_path

    artifacts.append(
        ResearchRunArtifact(
            kind=ResearchArtifactKind.REPORT,
            path=artifact_path,
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
            pdf_path = (report_path or cached_report_path).with_suffix(".pdf")
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

    # Non-fatal post-run ingest into knowledge vault if configured
    if _KNOWLEDGE_AVAILABLE and getattr(config.research, "knowledge_vault_enabled", True):
        try:
            ingest_result = ingest_session(session, markdown_report)
            if ingest_result.warnings:
                warnings.extend([f"[knowledge] {w}" for w in ingest_result.warnings])
        except Exception as exc:
            warnings.append(f"[knowledge] ingest failed: {exc}")

    try:
        store.save_session(session)
    except Exception as error:  # pragma: no cover - persistence boundary
        logger.exception("Unable to persist final metadata for session %s", session.session_id)
        warnings.append(
            "Failed to persist final report metadata; report cache remains available "
            f"({type(error).__name__})."
        )

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


def _build_recovery_markdown(
    session: ResearchSession,
    analysis: dict[str, Any],
) -> str:
    """Build a dependency-free report from whatever research data survived."""
    findings = _as_text_items(analysis.get("key_findings"))
    themes = _as_text_items(analysis.get("themes"))
    gaps = _as_text_items(analysis.get("gaps"))

    lines = [
        f"# Recovery report: {session.query}",
        "",
        "> The primary report pipeline failed. This recovery report preserves the partial "
        "research data that was available at finalization time.",
        "",
        "## Key Findings",
        "",
        *(_markdown_bullets(findings) or ["- No finalized findings were available."]),
        "",
        "## Themes",
        "",
        *(_markdown_bullets(themes) or ["- No finalized themes were available."]),
        "",
        "## Evidence Gaps",
        "",
        *(_markdown_bullets(gaps) or ["- Evidence collection or analysis was incomplete."]),
        "",
        "## Sources",
        "",
    ]

    if session.sources:
        for index, source in enumerate(session.sources, 1):
            title = source.title or source.url or f"Source {index}"
            if source.url:
                lines.append(f"{index}. [{title}]({source.url})")
            else:
                lines.append(f"{index}. {title}")
            if source.snippet:
                lines.append(f"   - {' '.join(source.snippet.split())}")
    else:
        lines.append("- No source records were available.")

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- This report was generated in recovery mode after an optional or primary "
            "reporting stage failed.",
            "- Treat incomplete findings as provisional and review the session telemetry "
            "before relying on them.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _render_recovery_report(
    output_format: ResearchOutputFormat,
    *,
    markdown_report: str,
    session: ResearchSession,
    analysis: dict[str, Any],
    warning: str,
) -> str:
    """Render a recovery report without depending on the failed reporter."""
    if output_format == ResearchOutputFormat.JSON:
        return json.dumps(
            {
                "session_id": session.session_id,
                "query": session.query,
                "depth": session.depth.value,
                "recovery_mode": True,
                "warning": warning,
                "analysis": analysis,
                "sources": [source.model_dump(mode="json") for source in session.sources],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    if output_format == ResearchOutputFormat.HTML:
        return (
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{escape(session.query)}</title></head><body>"
            f"<pre>{escape(markdown_report)}</pre></body></html>"
        )
    return markdown_report


def _as_text_items(value: Any) -> list[str]:
    """Normalize a partial analysis collection for recovery output."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _degradation_reasons(session: ResearchSession) -> list[str]:
    """Return normalized durable degradation reasons for one session."""
    reasons = session.metadata.get("execution", {}).get("degraded_reasons", [])
    if not isinstance(reasons, list):
        return []
    return [reason for reason in reasons if isinstance(reason, str)]


def _markdown_bullets(items: list[str]) -> list[str]:
    """Format recovery-report list items."""
    return [f"- {item}" for item in items]


def _media_type_for_format(output_format: ResearchOutputFormat) -> str:
    """Map a report format to the response media type."""
    if output_format == ResearchOutputFormat.JSON:
        return "application/json"
    if output_format == ResearchOutputFormat.HTML:
        return "text/html"
    return "text/markdown"
