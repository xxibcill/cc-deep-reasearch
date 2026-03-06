"""Core data structures for CC Deep Research CLI."""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ResearchDepth(StrEnum):
    """Research depth modes."""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class SearchOptions(BaseModel):
    """Options for search operations."""

    max_results: int = Field(default=10, ge=1, le=100)
    include_raw_content: bool = Field(default=True)
    search_depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    monitor: bool = Field(default=False)


class SearchResultItem(BaseModel):
    """A single search result item."""

    url: str = Field(..., min_length=1)
    title: str = Field(default="")
    snippet: str = Field(default="")
    content: str | None = Field(default=None)
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


class ProviderStatus(StrEnum):
    """Availability state for configured search providers."""

    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class DeepAnalysisStatus(StrEnum):
    """Execution state for the deep-analysis phase."""

    NOT_REQUESTED = "not_requested"
    COMPLETED = "completed"
    DEGRADED = "degraded"


class SessionProvidersMetadata(BaseModel):
    """Stable provider-resolution metadata for a research session."""

    configured: list[str] = Field(default_factory=list)
    available: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: ProviderStatus = Field(default=ProviderStatus.UNAVAILABLE)

    model_config = {"extra": "allow"}


class SessionExecutionMetadata(BaseModel):
    """Stable execution metadata for a research session."""

    parallel_requested: bool = Field(default=False)
    parallel_used: bool = Field(default=False)
    degraded: bool = Field(default=False)
    degraded_reasons: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class SessionDeepAnalysisMetadata(BaseModel):
    """Stable deep-analysis metadata for a research session."""

    requested: bool = Field(default=False)
    completed: bool = Field(default=False)
    status: DeepAnalysisStatus = Field(default=DeepAnalysisStatus.NOT_REQUESTED)
    reason: str | None = Field(default=None)

    model_config = {"extra": "allow"}


class SessionMetadataContract(BaseModel):
    """Stable top-level shape for ``ResearchSession.metadata``."""

    strategy: dict[str, Any] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    iteration_history: list[dict[str, Any]] = Field(default_factory=list)
    providers: SessionProvidersMetadata = Field(default_factory=SessionProvidersMetadata)
    execution: SessionExecutionMetadata = Field(default_factory=SessionExecutionMetadata)
    deep_analysis: SessionDeepAnalysisMetadata = Field(default_factory=SessionDeepAnalysisMetadata)

    model_config = {"extra": "allow"}


def _list_of_strings(value: Any) -> list[str]:
    """Coerce a metadata field into a list of strings."""
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _mapping_dict(value: Any) -> dict[str, Any]:
    """Coerce a mapping-like metadata field into a mutable dictionary."""
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _build_provider_metadata(
    raw_metadata: Mapping[str, Any],
    configured_providers: list[str],
) -> SessionProvidersMetadata:
    """Normalize provider metadata from legacy or explicit payloads."""
    raw_providers = raw_metadata.get("providers", {})
    provider_payload = (
        {"configured": raw_providers}
        if isinstance(raw_providers, list)
        else _mapping_dict(raw_providers)
    )

    configured = _list_of_strings(
        provider_payload.get("configured", configured_providers)
    ) or list(configured_providers)
    available = _list_of_strings(provider_payload.get("available", []))
    warnings = _list_of_strings(provider_payload.get("warnings", []))

    if available and not warnings and set(available) == set(configured):
        status = ProviderStatus.READY
    elif available:
        status = ProviderStatus.DEGRADED
    else:
        status = ProviderStatus.UNAVAILABLE

    return SessionProvidersMetadata(
        configured=configured,
        available=available,
        warnings=warnings,
        status=provider_payload.get("status", status),
    )


def _build_deep_analysis_metadata(
    raw_metadata: Mapping[str, Any],
    depth: "ResearchDepth",
    analysis: Mapping[str, Any],
) -> SessionDeepAnalysisMetadata:
    """Normalize deep-analysis metadata from legacy or explicit payloads."""
    requested = depth == ResearchDepth.DEEP
    raw_deep_analysis = raw_metadata.get("deep_analysis", {})
    deep_payload = (
        {"completed": raw_deep_analysis}
        if isinstance(raw_deep_analysis, bool)
        else _mapping_dict(raw_deep_analysis)
    )

    completed = bool(
        deep_payload.get(
            "completed",
            analysis.get("deep_analysis_complete", False),
        )
    )
    analysis_method = str(analysis.get("analysis_method", ""))

    degraded_methods = {"empty", "shallow_keyword"}

    if not requested:
        status = DeepAnalysisStatus.NOT_REQUESTED
        reason = None
    elif completed and analysis_method not in degraded_methods:
        status = DeepAnalysisStatus.COMPLETED
        reason = None
    else:
        status = DeepAnalysisStatus.DEGRADED
        reason = deep_payload.get(
            "reason",
            "Deep analysis requested but full multi-pass output was unavailable.",
        )

    return SessionDeepAnalysisMetadata(
        requested=deep_payload.get("requested", requested),
        completed=completed,
        status=deep_payload.get("status", status),
        reason=reason,
    )


def normalize_session_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    depth: "ResearchDepth",
    configured_providers: list[str] | None = None,
) -> dict[str, Any]:
    """Return a stable metadata contract for a research session.

    The normalized contract always includes the same top-level keys:
    ``strategy``, ``analysis``, ``validation``, ``iteration_history``,
    ``providers``, ``execution``, and ``deep_analysis``.
    """
    raw_metadata = dict(metadata or {})
    configured = list(configured_providers or [])
    analysis = _mapping_dict(raw_metadata.get("analysis", {}))
    providers = _build_provider_metadata(raw_metadata, configured)
    deep_analysis = _build_deep_analysis_metadata(raw_metadata, depth, analysis)

    raw_execution = _mapping_dict(raw_metadata.get("execution", {}))
    degraded_reasons = _list_of_strings(raw_execution.get("degraded_reasons", []))
    if providers.status != ProviderStatus.READY:
        degraded_reasons.extend(providers.warnings)
    if deep_analysis.status == DeepAnalysisStatus.DEGRADED and deep_analysis.reason:
        degraded_reasons.append(deep_analysis.reason)
    degraded_reasons = list(dict.fromkeys(degraded_reasons))

    contract = SessionMetadataContract(
        strategy=_mapping_dict(raw_metadata.get("strategy", {})),
        analysis=analysis,
        validation=_mapping_dict(raw_metadata.get("validation", {})),
        iteration_history=[
            _mapping_dict(item)
            for item in raw_metadata.get("iteration_history", [])
            if isinstance(item, Mapping)
        ],
        providers=providers,
        execution=SessionExecutionMetadata(
            parallel_requested=bool(raw_execution.get("parallel_requested", False)),
            parallel_used=bool(raw_execution.get("parallel_used", False)),
            degraded=bool(raw_execution.get("degraded", bool(degraded_reasons))),
            degraded_reasons=degraded_reasons,
        ),
        deep_analysis=deep_analysis,
    )
    return contract.model_dump(mode="python")


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


class ResearchSession(BaseModel):
    """Represents a complete research session."""

    session_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
    searches: list[SearchResult] = Field(default_factory=list)
    sources: list[SearchResultItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": False}

    @model_validator(mode="after")
    def _normalize_metadata(self) -> "ResearchSession":
        """Normalize session metadata into the stable contract."""
        self.metadata = normalize_session_metadata(
            self.metadata,
            depth=self.depth,
        )
        return self

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


class SearchMode(StrEnum):
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
