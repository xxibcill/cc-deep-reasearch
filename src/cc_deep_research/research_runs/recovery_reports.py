"""Dependency-free rendering for partial and terminal recovery reports."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from cc_deep_research.models import ResearchSession
from cc_deep_research.research_runs.models import ResearchOutputFormat


class RecoveryReportRenderer:
    """Render a report without relying on optional reporting dependencies."""

    def render(
        self,
        output_format: ResearchOutputFormat,
        *,
        session: ResearchSession,
        analysis: dict[str, Any],
        warning: str | None = None,
        terminal_status: str | None = None,
    ) -> tuple[str, str]:
        """Return both canonical Markdown and the requested representation."""
        markdown_report = self.generate_markdown_report(
            session,
            analysis,
            warning=warning,
            terminal_status=terminal_status,
        )
        if output_format == ResearchOutputFormat.JSON:
            report_content = self.generate_json_report(
                session,
                analysis,
                warning=warning,
                terminal_status=terminal_status,
            )
        elif output_format == ResearchOutputFormat.HTML:
            report_content = self.render_html_report(markdown_report, title=session.query)
        else:
            report_content = markdown_report
        return markdown_report, report_content

    def generate_markdown_report(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
        *,
        warning: str | None = None,
        terminal_status: str | None = None,
    ) -> str:
        """Build a transparent report from the evidence available at finalization."""
        findings = _as_text_items(analysis.get("key_findings"))
        themes = _as_text_items(analysis.get("themes"))
        gaps = _as_text_items(analysis.get("gaps"))
        reasons = _failure_reasons(session)
        if warning:
            reasons = [warning, *reasons]

        lines = [
            f"# Recovery report: {session.query}",
            "",
            _recovery_notice(terminal_status),
            "",
        ]
        if reasons:
            lines.extend(["## Execution Summary", "", *_markdown_bullets(reasons), ""])
        lines.extend(
            [
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
        )
        if session.sources:
            for index, source in enumerate(session.sources, 1):
                title = source.title or source.url or f"Source {index}"
                lines.append(
                    f"{index}. [{title}]({source.url})" if source.url else f"{index}. {title}"
                )
                if source.snippet:
                    lines.append(f"   - {' '.join(source.snippet.split())}")
        else:
            lines.append("- No source records were available.")
        lines.extend(
            [
                "",
                "## Limitations",
                "",
                "- This report was generated in recovery mode from incomplete execution data.",
                "- Treat incomplete findings as provisional and review the session telemetry before relying on them.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def generate_json_report(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
        *,
        warning: str | None = None,
        terminal_status: str | None = None,
    ) -> str:
        """Build the JSON representation of a recovery report."""
        payload: dict[str, Any] = {
            "session_id": session.session_id,
            "query": session.query,
            "depth": session.depth.value,
            "recovery_mode": True,
        }
        if warning is not None:
            payload["warning"] = warning
        if terminal_status is not None:
            payload["terminal_status"] = terminal_status
            payload["failure_reasons"] = _failure_reasons(session)
        payload["analysis"] = analysis
        payload["sources"] = [source.model_dump(mode="json") for source in session.sources]
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    def render_html_report(
        self, markdown_report: str, *, title: str = "Research recovery report"
    ) -> str:
        """Render recovery Markdown without optional report dependencies."""
        return (
            '<!doctype html><html><head><meta charset="utf-8">'
            f"<title>{escape(title)}</title></head><body>"
            f"<pre>{escape(markdown_report)}</pre></body></html>"
        )


def _recovery_notice(terminal_status: str | None) -> str:
    if terminal_status == "failed":
        return (
            "> The research workflow did not complete successfully after bounded automatic "
            "recovery. This report preserves the terminal state and limitations."
        )
    return (
        "> The primary report pipeline failed. This recovery report preserves the partial "
        "research data that was available at finalization time."
    )


def _as_text_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _failure_reasons(session: ResearchSession) -> list[str]:
    reasons = session.metadata.get("execution", {}).get("degraded_reasons", [])
    if not isinstance(reasons, list):
        return []
    return [reason for reason in reasons if isinstance(reason, str)]


def _markdown_bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


__all__ = ["RecoveryReportRenderer"]
