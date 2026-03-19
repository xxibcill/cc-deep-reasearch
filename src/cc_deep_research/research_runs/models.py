"""Shared models for reusable research-run execution."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

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


class DeletedLayer(BaseModel):
    """Result of deleting a single storage layer."""

    layer: str = Field(..., description="Layer identifier (session, telemetry, duckdb)")
    deleted: bool = Field(..., description="Whether deletion occurred")
    missing: bool = Field(default=False, description="True if layer did not exist")
    error: str | None = Field(default=None, description="Error message if deletion failed")


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

    @property
    def all_deleted(self) -> bool:
        """Return True if all present layers were successfully deleted."""
        return all(
            (layer.deleted or layer.missing) for layer in self.deleted_layers
        )

    @property
    def not_found(self) -> bool:
        """Return True if session was not found in any layer."""
        return all(layer.missing for layer in self.deleted_layers)


class SessionDeleteError(BaseModel):
    """Typed error response for session deletion."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    session_id: str = Field(..., description="The session_id that caused the error")
    active_conflict: bool = Field(default=False)


class ResearchRunCancelled(RuntimeError):
    """Raised when an operator stops a browser-started research run."""
