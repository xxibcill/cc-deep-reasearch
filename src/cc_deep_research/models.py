"""Core data structures for CC Deep Research CLI."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResearchDepth(str, Enum):
    """Research depth modes."""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class SearchOptions(BaseModel):
    """Options for search operations."""

    max_results: int = Field(default=10, ge=1, le=100)
    include_raw_content: bool = Field(default=False)
    search_depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    monitor: bool = Field(default=False)


class SearchResultItem(BaseModel):
    """A single search result item."""

    url: str = Field(..., min_length=1)
    title: str = Field(default="")
    snippet: str = Field(default="")
    content: Optional[str] = Field(default=None)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": False}


class SearchResult(BaseModel):
    """Result from a search operation."""

    query: str = Field(..., min_length=1)
    results: list[SearchResultItem] = Field(default_factory=list)
    provider: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    execution_time_ms: int = Field(default=0, ge=0)


class APIKey(BaseModel):
    """Represents an API key with usage tracking."""

    key: str = Field(..., min_length=1)
    requests_used: int = Field(default=0, ge=0)
    requests_limit: int = Field(default=1000, ge=1)
    last_used: Optional[datetime] = Field(default=None)
    disabled: bool = Field(default=False)

    @property
    def is_available(self) -> bool:
        """Check if this key is available for use."""
        return not self.disabled and self.requests_used < self.requests_limit

    @property
    def remaining_requests(self) -> int:
        """Get remaining requests for this key."""
        return max(0, self.requests_limit - self.requests_used)


class ResearchSession(BaseModel):
    """Represents a complete research session."""

    session_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    searches: list[SearchResult] = Field(default_factory=list)
    sources: list[SearchResultItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def execution_time_seconds(self) -> float:
        """Get total execution time in seconds."""
        if self.completed_at is None:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def total_sources(self) -> int:
        """Get total number of unique sources."""
        return len(self.sources)


class SearchMode(str, Enum):
    """Search mode for orchestrator."""

    HYBRID_PARALLEL = "hybrid_parallel"
    TAVILY_PRIMARY = "tavily_primary"
    CLAUDE_PRIMARY = "claude_primary"


class QualityScore(BaseModel):
    """Quality score for a source."""

    credibility: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness: float = Field(default=0.5, ge=0.0, le=1.0)
    diversity: float = Field(default=0.5, ge=0.0, le=1.0)
    overall: float = Field(default=0.5, ge=0.0, le=1.0)


class CrossReferenceClaim(BaseModel):
    """A claim found across multiple sources."""

    claim: str
    supporting_sources: list[str] = Field(default_factory=list)  # URLs
    contradicting_sources: list[str] = Field(default_factory=list)  # URLs
    consensus_level: float = Field(default=0.0, ge=0.0, le=1.0)
