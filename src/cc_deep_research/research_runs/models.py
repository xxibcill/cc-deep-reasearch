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

