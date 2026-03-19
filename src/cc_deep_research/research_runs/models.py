"""Shared models for reusable research-run execution."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from cc_deep_research.models import ResearchDepth, ResearchSession


class ResearchOutputFormat(StrEnum):
    """Supported final report formats."""

    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"


class ResearchArtifactKind(StrEnum):
    """Persisted artifact categories for a completed research run."""

    SESSION = "session"
    REPORT = "report"
    PDF = "pdf"


class ResearchRunStatus(StrEnum):
    """Lifecycle states exposed by the research-run API."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


MAX_BULK_DELETE_SESSION_IDS = 25


class ResearchRunRequest(BaseModel):
    """Framework-agnostic request contract for a research run."""

    query: str = Field(..., min_length=1)
    depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    min_sources: int | None = Field(default=None, ge=1)
    output_path: Path | None = Field(default=None)
    output_format: ResearchOutputFormat = Field(default=ResearchOutputFormat.MARKDOWN)
    search_providers: list[str] | None = Field(default=None)
    cross_reference_enabled: bool | None = Field(default=None)
    team_size: int | None = Field(default=None, ge=2, le=8)
    parallel_mode: bool | None = Field(default=None)
    num_researchers: int | None = Field(default=None, ge=1, le=8)
    realtime_enabled: bool = Field(default=False)
    pdf_enabled: bool = Field(default=False)

    @field_validator("search_providers")
    @classmethod
    def normalize_search_providers(cls, value: list[str] | None) -> list[str] | None:
        """Normalize provider names while preserving first-seen order."""
        if value is None:
            return None

        normalized: list[str] = []
        seen: set[str] = set()
        for candidate in value:
            provider = candidate.strip().lower()
            if not provider or provider in seen:
                continue
            seen.add(provider)
            normalized.append(provider)
        return normalized or None


class ResearchRunArtifact(BaseModel):
    """Metadata for one persisted artifact produced by a research run."""

    kind: ResearchArtifactKind
    path: Path
    format: str | None = Field(default=None)
    media_type: str | None = Field(default=None)


class ResearchRunReport(BaseModel):
    """Final report metadata returned to the caller."""

    format: ResearchOutputFormat
    content: str
    path: Path | None = Field(default=None)
    media_type: str


class ResearchRunResult(BaseModel):
    """Typed result for a completed research run."""

    session: ResearchSession
    report: ResearchRunReport
    artifacts: list[ResearchRunArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def session_id(self) -> str:
        """Return the completed session identifier."""
        return self.session.session_id


class ResearchRunStatusResponse(BaseModel):
    """Polling payload for one browser-started research run."""

    run_id: str
    status: ResearchRunStatus
    created_at: str
    session_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    result: dict[str, object] | None = None
    stop_requested: bool = False


class ResearchRunStopResponse(BaseModel):
    """Response returned when an operator requests a stop."""

    run_id: str
    status: ResearchRunStatus
    stop_requested: bool
    session_id: str | None = None


class SessionDeleteRequest(BaseModel):
    """Contract for a single-session hard delete request."""

    session_id: str = Field(..., min_length=1, description="The session to delete")
    force: bool = Field(
        default=False,
        description="If true, delete even if session is currently active",
    )


class BulkSessionDeleteRequest(BaseModel):
    """Contract for bounded multi-session hard delete requests."""

    session_ids: list[str] = Field(
        ...,
        description="Ordered session ids to delete in one request",
    )
    force: bool = Field(
        default=False,
        description="If true, delete even if sessions are currently active",
    )

    @field_validator("session_ids")
    @classmethod
    def normalize_session_ids(cls, value: list[str]) -> list[str]:
        """Trim ids, drop duplicates, and enforce a conservative batch size."""
        normalized: list[str] = []
        seen: set[str] = set()

        for candidate in value:
            session_id = candidate.strip()
            if not session_id:
                raise ValueError("session_ids must contain non-empty strings")
            if session_id in seen:
                continue
            seen.add(session_id)
            normalized.append(session_id)

        if not normalized:
            raise ValueError("session_ids must contain at least one session id")
        if len(normalized) > MAX_BULK_DELETE_SESSION_IDS:
            raise ValueError(
                f"bulk delete is limited to {MAX_BULK_DELETE_SESSION_IDS} session ids per request"
            )
        return normalized


class DeletedLayer(BaseModel):
    """Result of deleting a single storage layer."""

    layer: str = Field(..., description="Layer identifier (session, telemetry, duckdb)")
    deleted: bool = Field(..., description="Whether deletion occurred")
    missing: bool = Field(default=False, description="True if layer did not exist")
    error: str | None = Field(default=None, description="Error message if deletion failed")


class SessionDeleteOutcome(StrEnum):
    """Operator-facing delete result state for one session."""

    DELETED = "deleted"
    NOT_FOUND = "not_found"
    ACTIVE_CONFLICT = "active_conflict"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class SessionDeleteResponse(BaseModel):
    """Contract for session delete operation response."""

    session_id: str = Field(..., description="The requested session_id")
    success: bool = Field(..., description="True if at least one layer was deleted")
    deleted_layers: list[DeletedLayer] = Field(
        default_factory=list,
        description="Results per storage layer",
    )
    active_conflict: bool = Field(
        default=False,
        description="True if session is active and force=false",
    )
    error: str | None = Field(
        default=None,
        description="Top-level error when the purge could not complete one session",
    )
    outcome: SessionDeleteOutcome = Field(
        default=SessionDeleteOutcome.FAILED,
        description="Normalized operator-facing outcome for this session",
    )

    @property
    def all_deleted(self) -> bool:
        """Return True if all present layers were successfully deleted."""
        return bool(self.deleted_layers) and all(
            (layer.deleted or layer.missing) for layer in self.deleted_layers
        )

    @property
    def not_found(self) -> bool:
        """Return True if session was not found in any layer."""
        return bool(self.deleted_layers) and all(layer.missing for layer in self.deleted_layers)

    @property
    def has_errors(self) -> bool:
        """Return True if any layer or top-level purge failure was recorded."""
        return self.error is not None or any(layer.error for layer in self.deleted_layers)

    @model_validator(mode="after")
    def infer_outcome(self) -> SessionDeleteResponse:
        """Derive a stable per-session outcome from delete-layer results."""
        if self.active_conflict:
            self.outcome = SessionDeleteOutcome.ACTIVE_CONFLICT
            return self

        if self.error is not None:
            self.outcome = SessionDeleteOutcome.FAILED
            return self

        if self.not_found:
            self.outcome = SessionDeleteOutcome.NOT_FOUND
            return self

        if self.success and self.all_deleted and not self.has_errors:
            self.outcome = SessionDeleteOutcome.DELETED
            return self

        if self.success and (self.has_errors or not self.all_deleted):
            self.outcome = SessionDeleteOutcome.PARTIAL_FAILURE
            return self

        self.outcome = SessionDeleteOutcome.FAILED
        return self


class BulkSessionDeleteSummary(BaseModel):
    """Aggregate counts for a bulk delete response."""

    requested_count: int
    deleted_count: int
    not_found_count: int
    active_conflict_count: int
    partial_failure_count: int
    failed_count: int


class BulkSessionDeleteResponse(BaseModel):
    """Contract for bulk delete responses with per-session outcomes."""

    success: bool = Field(
        ...,
        description="True if every requested session resolved without conflicts or failures",
    )
    partial_success: bool = Field(
        ...,
        description="True if at least one session resolved cleanly and at least one did not",
    )
    results: list[SessionDeleteResponse] = Field(
        default_factory=list,
        description="Per-session delete outcomes in request order",
    )
    summary: BulkSessionDeleteSummary

    @classmethod
    def from_results(cls, results: list[SessionDeleteResponse]) -> BulkSessionDeleteResponse:
        """Build aggregate flags and counts from per-session results."""
        deleted_count = sum(
            1 for result in results if result.outcome == SessionDeleteOutcome.DELETED
        )
        not_found_count = sum(
            1 for result in results if result.outcome == SessionDeleteOutcome.NOT_FOUND
        )
        active_conflict_count = sum(
            1 for result in results if result.outcome == SessionDeleteOutcome.ACTIVE_CONFLICT
        )
        partial_failure_count = sum(
            1 for result in results if result.outcome == SessionDeleteOutcome.PARTIAL_FAILURE
        )
        failed_count = sum(
            1 for result in results if result.outcome == SessionDeleteOutcome.FAILED
        )
        requested_count = len(results)
        clean_count = deleted_count + not_found_count

        return cls(
            success=(active_conflict_count + partial_failure_count + failed_count) == 0,
            partial_success=clean_count > 0
            and (active_conflict_count + partial_failure_count + failed_count) > 0,
            results=results,
            summary=BulkSessionDeleteSummary(
                requested_count=requested_count,
                deleted_count=deleted_count,
                not_found_count=not_found_count,
                active_conflict_count=active_conflict_count,
                partial_failure_count=partial_failure_count,
                failed_count=failed_count,
            ),
        )


class SessionDeleteError(BaseModel):
    """Typed error response for session deletion."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    session_id: str = Field(..., description="The session_id that caused the error")
    active_conflict: bool = Field(default=False)


class ResearchRunCancelled(RuntimeError):
    """Raised when an operator stops a browser-started research run."""
