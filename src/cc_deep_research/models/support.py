"""Shared support models and compatibility re-exports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .quality import (
    ClaimEvidence,
    ClaimFreshness,
    CrossReferenceClaim,
    EvidenceType,
    QualityScore,
    ReportEvaluationResult,
    ResearchGapType,
    SourceType,
)


class SearchMode(StrEnum):
    """Search mode for orchestrator."""

    HYBRID_PARALLEL = "hybrid_parallel"
    TAVILY_PRIMARY = "tavily_primary"
    CLAUDE_PRIMARY = "claude_primary"


class APIKey(BaseModel):
    """Represents an API key with usage tracking."""

    key: str = Field(..., min_length=1)
    requests_used: int = Field(default=0, ge=0)
    requests_limit: int = Field(default=1000, ge=1)
    last_used: datetime | None = Field(default=None)
    disabled: bool = Field(default=False)

    @property
    def is_available(self) -> bool:
        """Check if this key is available for use."""
        return not self.disabled and self.requests_used < self.requests_limit

    @property
    def remaining_requests(self) -> int:
        """Get remaining requests for this key."""
        return max(0, self.requests_limit - self.requests_used)


__all__ = [
    "APIKey",
    "ClaimEvidence",
    "ClaimFreshness",
    "CrossReferenceClaim",
    "EvidenceType",
    "QualityScore",
    "ReportEvaluationResult",
    "ResearchGapType",
    "SearchMode",
    "SourceType",
]
