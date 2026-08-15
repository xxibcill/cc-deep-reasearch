"""Bounded automatic recovery policy for browser-started research runs."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from html import escape
from pathlib import Path
from typing import Any

from cc_deep_research.models import ResearchSession
from cc_deep_research.persistence import atomic_write_text
from cc_deep_research.research_runs.models import (
    ResearchArtifactKind,
    ResearchOutputFormat,
    ResearchRunArtifact,
    ResearchRunCancelled,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchWorkflow,
)
from cc_deep_research.research_runs.resume import (
    ResearchResumeSnapshotError,
    ResearchResumeState,
    ResearchResumeStore,
)
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import get_default_telemetry_dir, query_session_checkpoints

logger = logging.getLogger(__name__)

_NON_RETRIABLE_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    KeyError,
    NotImplementedError,
    ResearchRunCancelled,
    TypeError,
    ValueError,
)


class RecoveryStrategy(StrEnum):
    """Supported job-level automatic recovery strategies."""

    CHECKPOINT_RESUME = "checkpoint_resume"
    ALTERNATE_EXECUTION = "alternate_execution"


class RecoveryOutcome(StrEnum):
    """Terminal outcome for one automatic recovery attempt."""

    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RecoveryCheckpoint:
    """Checksum-verified checkpoint selected for automatic recovery."""

    session_id: str
    checkpoint_id: str
    state: ResearchResumeState


@dataclass(frozen=True, slots=True)
class RecoveryAttempt:
    """Durable summary of one bounded automatic recovery attempt."""

    strategy: str
    outcome: str
    session_id: str | None = None
    checkpoint_id: str | None = None
    reason: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        """Return JSON-compatible session metadata."""
        return {key: value for key, value in asdict(self).items() if value is not None}


class FailureReportGenerator:
    """Dependency-free reporter used after every execution path has failed."""

    def generate_markdown_report(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Build a transparent final report from the failed session payload."""
        reasons = _execution_failure_reasons(session)
        reason_lines = [f"- {reason}" for reason in reasons] or [
            "- Research execution stopped before a validated result was available."
        ]
        finding_lines = [
            f"- {_finding_text(finding)}"
            for finding in analysis.get("key_findings", [])
            if _finding_text(finding)
        ] or ["- No findings were validated before execution stopped."]
        source_lines = [
            f"- [{source.title or source.url}]({source.url})"
            + (f" — {source.snippet}" if source.snippet else "")
            for source in session.sources
        ] or ["- No usable source set was available for a final synthesis."]
        return "\n".join(
            [
                f"# Recovery report: {session.query}",
                "",
                "> The research workflow did not complete successfully after bounded automatic "
                "recovery. This report preserves the terminal state and limitations.",
                "",
                "## Execution Summary",
                "",
                *reason_lines,
                "",
                "## Key Findings",
                "",
                *finding_lines,
                "",
                "## Sources",
                "",
                *source_lines,
                "",
                "## Limitations",
                "",
                "- Do not treat this recovery report as a completed evidence review.",
                "- Review the session telemetry and retry after correcting unavailable services "
                "or invalid configuration.",
                "",
            ]
        )

    def generate_json_report(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Build the JSON representation of the terminal recovery state."""
        return json.dumps(
            {
                "session_id": session.session_id,
                "query": session.query,
                "depth": session.depth.value,
                "recovery_mode": True,
                "terminal_status": "failed",
                "failure_reasons": _execution_failure_reasons(session),
                "analysis": analysis,
                "sources": [source.model_dump(mode="json") for source in session.sources],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    def render_html_report(self, markdown_report: str) -> str:
        """Render recovery Markdown without optional report dependencies."""
        return (
            '<!doctype html><html><head><meta charset="utf-8">'
            "<title>Research recovery report</title></head><body>"
            f"<pre>{escape(markdown_report)}</pre></body></html>"
        )


def is_terminal_failure(result: ResearchRunResult) -> bool:
    """Return whether a materialized result still represents a failed run."""
    metadata = result.session.metadata
    execution = metadata.get("execution", {})
    terminal_status = execution.get("terminal_status")
    if isinstance(terminal_status, str):
        return terminal_status == "failed"
    if result.session.total_sources > 0:
        return False

    providers = metadata.get("providers", {})
    if providers.get("status") == "unavailable":
        return True
    degraded_reasons = execution.get("degraded_reasons", [])
    return any(
        isinstance(reason, str) and reason.startswith("All initialized providers failed")
        for reason in degraded_reasons
    )


def is_retriable_failure(error: Exception) -> bool:
    """Reject deterministic programming/configuration errors from automatic retry."""
    return not isinstance(error, _NON_RETRIABLE_EXCEPTIONS)


def safe_failure_reason(stage: str, error: Exception) -> str:
    """Build a user-safe failure reason without leaking provider payloads or secrets."""
    return f"{stage} failed ({type(error).__name__})."


def build_alternate_recovery_request(request: ResearchRunRequest) -> ResearchRunRequest:
    """Build a fresh request that exercises a distinct, lower-concurrency path."""
    configured_providers = set(request.search_providers or [])
    alternate_provider = (
        "tavily_advanced" if configured_providers == {"tavily_basic"} else "tavily_basic"
    )
    alternate_workflow = (
        ResearchWorkflow.PLANNER
        if request.workflow == ResearchWorkflow.STAGED
        else ResearchWorkflow.STAGED
    )
    return request.model_copy(
        update={
            "workflow": alternate_workflow,
            "search_providers": [alternate_provider],
            "concurrent_source_collection": False,
            "max_concurrent_sources": 1,
        }
    )


def load_latest_recovery_checkpoint(
    session_id: str,
    *,
    telemetry_dir: Path | None = None,
    resume_store: ResearchResumeStore | None = None,
) -> RecoveryCheckpoint | None:
    """Load the newest checksum-valid execution checkpoint for one failed session."""
    resolved_telemetry_dir = telemetry_dir or get_default_telemetry_dir()
    manifest = query_session_checkpoints(session_id, base_dir=resolved_telemetry_dir)
    store = resume_store or ResearchResumeStore(resolved_telemetry_dir)

    for candidate in reversed(manifest.get("checkpoints", [])):
        if not _is_executable_checkpoint(candidate):
            continue
        try:
            state = store.load(session_id, str(candidate["state_ref"]))
        except ResearchResumeSnapshotError:
            logger.warning(
                "Ignoring invalid automatic-recovery snapshot for session %s checkpoint %s",
                session_id,
                candidate.get("checkpoint_id"),
            )
            continue

        checkpoint_id = str(candidate["checkpoint_id"])
        state.origin_session_id = state.origin_session_id or session_id
        state.origin_checkpoint_id = checkpoint_id
        return RecoveryCheckpoint(
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            state=state,
        )
    return None


def _finding_text(finding: Any) -> str:
    """Return a compact display value for typed or serialized findings."""
    if isinstance(finding, str):
        return finding
    if isinstance(finding, dict):
        for key in ("finding", "claim", "summary", "text"):
            value = finding.get(key)
            if isinstance(value, str) and value:
                return value
    return str(finding) if finding is not None else ""


def _append_unique(existing: Any, additions: list[str]) -> list[Any]:
    """Append strings to a possibly typed list without discarding prior entries."""
    values = list(existing) if isinstance(existing, list) else []
    for addition in additions:
        if addition not in values:
            values.append(addition)
    return values


def _resume_evidence(
    recovery_state: ResearchResumeState | None,
) -> tuple[list[Any], dict[str, Any]]:
    """Extract sources and analysis already persisted in a resumable checkpoint."""
    if recovery_state is None:
        return [], {}
    if recovery_state.analysis is not None:
        return list(recovery_state.sources), recovery_state.analysis.model_dump(mode="json")
    if recovery_state.planner_synthesis is not None:
        synthesis = recovery_state.planner_synthesis
        return list(synthesis.all_sources), {
            "key_findings": list(synthesis.key_findings),
            "themes": list(synthesis.themes),
            "gaps": list(synthesis.gaps),
            "analysis_method": "planner_synthesis",
        }
    return list(recovery_state.sources), {}


def build_failed_research_session(
    request: ResearchRunRequest,
    *,
    session_id: str | None,
    failure_reasons: list[str],
    preserved_session: ResearchSession | None = None,
    recovery_state: ResearchResumeState | None = None,
) -> ResearchSession:
    """Create a terminal session while retaining every available piece of evidence."""
    normalized_reasons = list(dict.fromkeys(failure_reasons)) or [
        "Research execution failed before a detailed reason was available."
    ]
    resume_sources, resume_analysis = _resume_evidence(recovery_state)
    if preserved_session is not None:
        session = preserved_session.model_copy(deep=True)
    else:
        session = ResearchSession(
            session_id=session_id or f"research-failed-{uuid.uuid4().hex[:12]}",
            query=request.query,
            depth=request.depth,
            sources=resume_sources,
        )

    analysis = dict(resume_analysis)
    analysis.update(session.metadata.get("analysis", {}))
    analysis.setdefault("key_findings", [])
    analysis.setdefault("themes", [])
    analysis.setdefault("themes_detailed", [])
    analysis.setdefault("consensus_points", [])
    analysis.setdefault("contention_points", [])
    analysis["gaps"] = _append_unique(analysis.get("gaps", []), normalized_reasons)
    analysis.setdefault("analysis_method", "automatic_recovery_failure")

    execution = dict(session.metadata.get("execution", {}))
    execution["degraded"] = True
    execution["degraded_reasons"] = _append_unique(
        execution.get("degraded_reasons", []), normalized_reasons
    )
    execution["terminal_status"] = "failed"
    session.metadata["analysis"] = analysis
    session.metadata["execution"] = execution
    session.completed_at = datetime.now(UTC)
    return session


def materialize_failure_result(
    request: ResearchRunRequest,
    *,
    session_id: str | None,
    failure_reasons: list[str],
    session_store: SessionStore | None = None,
    preserved_session: ResearchSession | None = None,
    recovery_state: ResearchResumeState | None = None,
) -> ResearchRunResult:
    """Always return an in-memory report and persist it on a best-effort basis."""
    store = session_store or SessionStore()
    if preserved_session is None and session_id is not None:
        try:
            preserved_session = store.load_session(session_id)
        except Exception:  # pragma: no cover - corrupt persistence boundary
            logger.exception("Unable to load partial session %s", session_id)
    session = build_failed_research_session(
        request,
        session_id=session_id,
        failure_reasons=failure_reasons,
        preserved_session=preserved_session,
        recovery_state=recovery_state,
    )
    reporter = FailureReportGenerator()
    analysis = session.metadata["analysis"]
    markdown_report = reporter.generate_markdown_report(session, analysis)
    if request.output_format == ResearchOutputFormat.JSON:
        report_content = reporter.generate_json_report(session, analysis)
    elif request.output_format == ResearchOutputFormat.HTML:
        report_content = reporter.render_html_report(markdown_report)
    else:
        report_content = markdown_report

    warnings: list[str] = []
    artifacts: list[ResearchRunArtifact] = []
    try:
        session_path = store.save_session(session)
        artifacts.append(
            ResearchRunArtifact(
                kind=ResearchArtifactKind.SESSION,
                path=session_path,
                format="json",
                media_type="application/json",
            )
        )
    except Exception as error:  # pragma: no cover - persistence boundary
        logger.exception("Unable to persist failed session %s", session.session_id)
        warnings.append(f"Failed to persist terminal session metadata ({type(error).__name__}).")

    report_path: Path | None = None
    try:
        report_path = store.save_report(
            session.session_id,
            request.output_format,
            report_content,
        )
        if request.output_format != ResearchOutputFormat.MARKDOWN:
            store.save_report(
                session.session_id,
                ResearchOutputFormat.MARKDOWN,
                markdown_report,
            )
    except Exception as error:  # pragma: no cover - persistence boundary
        logger.exception("Unable to cache failure report for session %s", session.session_id)
        warnings.append(
            "Failed to cache the terminal report; the in-memory report remains available "
            f"({type(error).__name__})."
        )

    if request.output_path is not None:
        try:
            atomic_write_text(request.output_path, report_content)
        except OSError as error:
            logger.warning(
                "Unable to write requested failure report for session %s: %s",
                session.session_id,
                type(error).__name__,
            )
            warnings.append(
                f"Failed to write the requested terminal report path ({type(error).__name__})."
            )
        else:
            report_path = request.output_path

    if report_path is not None:
        artifacts.append(
            ResearchRunArtifact(
                kind=ResearchArtifactKind.REPORT,
                path=report_path,
                format=request.output_format.value,
                media_type=_media_type_for_format(request.output_format),
            )
        )
    if request.pdf_enabled:
        warnings.append("PDF generation was skipped for the terminal recovery report.")

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


def finalize_recovery_result(
    result: ResearchRunResult,
    *,
    attempts: list[RecoveryAttempt],
    failure_reasons: list[str],
    session_store: SessionStore | None = None,
) -> ResearchRunResult:
    """Attach recovery provenance and best-effort persist the final result metadata."""
    succeeded = not is_terminal_failure(result)
    result.session.metadata.setdefault("execution", {})["automatic_recovery"] = {
        "attempted": bool(attempts),
        "attempt_count": len(attempts),
        "succeeded": succeeded,
        "attempts": [attempt.to_metadata() for attempt in attempts],
        "failure_reasons": list(dict.fromkeys(failure_reasons)),
    }
    if succeeded:
        warning = f"Automatic recovery succeeded after {len(attempts)} attempt(s)."
    elif attempts:
        warning = "Automatic recovery was exhausted; a final recovery report was preserved."
    else:
        warning = "Execution could not be retried safely; a final recovery report was preserved."
    if warning not in result.warnings:
        result.warnings.append(warning)

    store = session_store or SessionStore()
    try:
        store.save_session(result.session)
        store.save_report(result.session_id, result.report.format, result.report.content)
    except Exception:
        logger.exception(
            "Unable to persist automatic recovery metadata for session %s",
            result.session_id,
        )
    return result


def _is_executable_checkpoint(candidate: Any) -> bool:
    """Return whether a manifest entry links to an executable resume snapshot."""
    if not isinstance(candidate, dict):
        return False
    metadata = candidate.get("metadata")
    return bool(
        candidate.get("resume_safe")
        and candidate.get("state_ref")
        and isinstance(metadata, dict)
        and metadata.get("execution_resume") is True
    )


def _execution_failure_reasons(session: ResearchSession) -> list[str]:
    """Read normalized failure reasons from session execution metadata."""
    reasons = session.metadata.get("execution", {}).get("degraded_reasons", [])
    if not isinstance(reasons, list):
        return []
    return [reason for reason in reasons if isinstance(reason, str)]


def _media_type_for_format(output_format: ResearchOutputFormat) -> str:
    """Return the media type for a terminal recovery report."""
    if output_format == ResearchOutputFormat.JSON:
        return "application/json"
    if output_format == ResearchOutputFormat.HTML:
        return "text/html"
    return "text/markdown"


__all__ = [
    "FailureReportGenerator",
    "RecoveryAttempt",
    "RecoveryCheckpoint",
    "RecoveryOutcome",
    "RecoveryStrategy",
    "build_alternate_recovery_request",
    "build_failed_research_session",
    "finalize_recovery_result",
    "is_retriable_failure",
    "is_terminal_failure",
    "load_latest_recovery_checkpoint",
    "materialize_failure_result",
    "safe_failure_reason",
]
