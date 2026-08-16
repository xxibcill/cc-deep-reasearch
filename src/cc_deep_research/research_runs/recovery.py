"""Bounded automatic recovery policy for browser-started research runs."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
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
from cc_deep_research.research_runs.recovery_reports import RecoveryReportRenderer
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

    strategy: RecoveryStrategy
    outcome: RecoveryOutcome
    session_id: str | None = None
    checkpoint_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        """Reject invalid states before they reach durable metadata."""
        if not isinstance(self.strategy, RecoveryStrategy):
            raise TypeError("strategy must be a RecoveryStrategy")
        if not isinstance(self.outcome, RecoveryOutcome):
            raise TypeError("outcome must be a RecoveryOutcome")

    def to_metadata(self) -> dict[str, Any]:
        """Return JSON-compatible session metadata."""
        metadata: dict[str, Any] = {
            "strategy": self.strategy.value,
            "outcome": self.outcome.value,
        }
        if self.session_id is not None:
            metadata["session_id"] = self.session_id
        if self.checkpoint_id is not None:
            metadata["checkpoint_id"] = self.checkpoint_id
        if self.reason is not None:
            metadata["reason"] = self.reason
        return metadata


FailureReportGenerator = RecoveryReportRenderer


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


def merge_research_session_evidence(
    *sessions: ResearchSession | None,
) -> ResearchSession | None:
    """Merge evidence from bounded attempts while retaining the latest session identity."""
    available = [session for session in sessions if session is not None]
    if not available:
        return None

    merged = available[-1].model_copy(deep=True)
    merged.sources = []
    seen_urls: set[str] = set()
    for session in available:
        for source in session.sources:
            if source.url in seen_urls:
                continue
            seen_urls.add(source.url)
            merged.sources.append(source.model_copy(deep=True))

    merged.searches = []
    seen_searches: set[tuple[str, str, datetime]] = set()
    for session in available:
        for search in session.searches:
            key = (search.query, search.provider, search.timestamp)
            if key in seen_searches:
                continue
            seen_searches.add(key)
            merged.searches.append(search.model_copy(deep=True))

    analysis: dict[str, Any] = {}
    for session in available:
        for key, value in session.metadata.get("analysis", {}).items():
            if isinstance(value, list):
                current = analysis.get(key)
                combined = list(current) if isinstance(current, list) else []
                for item in value:
                    if item not in combined:
                        combined.append(item)
                analysis[key] = combined
            elif isinstance(value, dict) and isinstance(analysis.get(key), dict):
                analysis[key] = {**analysis[key], **value}
            else:
                analysis[key] = value
    if analysis:
        merged.metadata["analysis"] = analysis
    return merged


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
    reporter = RecoveryReportRenderer()
    analysis = session.metadata["analysis"]
    markdown_report, report_content = reporter.render(
        request.output_format,
        session=session,
        analysis=analysis,
        terminal_status="failed",
    )

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
