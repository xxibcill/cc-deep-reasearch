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


class QueryProvenance(BaseModel):
    """Trace one source back to the query variation that produced it."""

    query: str = Field(..., min_length=1)
    family: str = Field(default="baseline")
    intent_tags: list[str] = Field(default_factory=list)


def _dedupe_strings(values: list[str]) -> list[str]:
    """Return unique strings in first-seen order."""
    return list(dict.fromkeys(value for value in values if value))


def _normalize_query_provenance_entries(value: Any) -> list[QueryProvenance]:
    """Coerce mixed provenance payloads into typed entries."""
    if isinstance(value, QueryProvenance):
        candidates: list[Any] = [value]
    elif isinstance(value, Mapping):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        return []

    normalized: list[QueryProvenance] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for candidate in candidates:
        try:
            entry = (
                candidate
                if isinstance(candidate, QueryProvenance)
                else QueryProvenance.model_validate(candidate)
            )
        except Exception:
            continue
        entry.intent_tags = _dedupe_strings([str(tag) for tag in entry.intent_tags])
        key = (entry.query, entry.family, tuple(entry.intent_tags))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(entry)
    return normalized


class SearchResultItem(BaseModel):
    """A single search result item."""

    url: str = Field(..., min_length=1)
    title: str = Field(default="")
    snippet: str = Field(default="")
    content: str | None = Field(default=None)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    query_provenance: list[QueryProvenance] = Field(default_factory=list)

    model_config = {"frozen": False}

    @model_validator(mode="after")
    def _normalize_provenance(self) -> "SearchResultItem":
        """Keep provenance fields synchronized with source metadata."""
        metadata = dict(self.source_metadata)
        provenance = _normalize_query_provenance_entries(self.query_provenance)

        if not provenance:
            provenance = _normalize_query_provenance_entries(metadata.get("query_provenance"))

        if not provenance and metadata.get("query"):
            provenance = _normalize_query_provenance_entries(
                {
                    "query": metadata.get("query"),
                    "family": metadata.get("query_family", "baseline"),
                    "intent_tags": metadata.get("query_intent_tags", []),
                }
            )

        self.query_provenance = provenance
        if not provenance:
            return self

        metadata["query_provenance"] = [
            entry.model_dump(mode="python") for entry in provenance
        ]
        metadata["queries"] = _dedupe_strings([entry.query for entry in provenance])
        metadata["query_families"] = _dedupe_strings([entry.family for entry in provenance])
        if len(provenance) == 1:
            metadata["query"] = provenance[0].query
            metadata["query_family"] = provenance[0].family
            metadata["query_intent_tags"] = list(provenance[0].intent_tags)
        else:
            metadata.pop("query", None)
            metadata.pop("query_family", None)
            metadata.pop("query_intent_tags", None)
        self.source_metadata = metadata
        return self

    def add_query_provenance(
        self,
        *,
        query: str,
        family: str = "baseline",
        intent_tags: list[str] | None = None,
    ) -> None:
        """Attach one query provenance entry to the source."""
        merged = _normalize_query_provenance_entries(
            [
                *self.query_provenance,
                {
                    "query": query,
                    "family": family,
                    "intent_tags": intent_tags or [],
                },
            ]
        )
        self.query_provenance = merged
        self._normalize_provenance()


class SearchResult(BaseModel):
    """Result from a search operation."""

    query: str = Field(..., min_length=1)
    results: list[SearchResultItem] = Field(default_factory=list)
    provider: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    execution_time_ms: int = Field(default=0, ge=0)


class QueryProfile(BaseModel):
    """Lightweight profile derived from the incoming research query."""

    intent: str = Field(default="informational")
    is_time_sensitive: bool = Field(default=False)
    key_terms: list[str] = Field(default_factory=list)
    target_source_classes: list[str] = Field(default_factory=list)


class QueryFamily(BaseModel):
    """A labeled query expansion with explicit retrieval purpose."""

    query: str = Field(..., min_length=1)
    family: str = Field(default="baseline")
    intent_tags: list[str] = Field(default_factory=list)


class StrategyPlan(BaseModel):
    """Planned workflow configuration for a research run."""

    query_variations: int = Field(default=1, ge=1)
    max_sources: int = Field(default=3, ge=1)
    enable_cross_ref: bool = Field(default=False)
    enable_quality_scoring: bool = Field(default=False)
    tasks: list[str] = Field(default_factory=list)
    follow_up_bias: str = Field(default="coverage")
    intent: str = Field(default="informational")
    time_sensitive: bool = Field(default=False)
    key_terms: list[str] = Field(default_factory=list)
    target_source_classes: list[str] = Field(default_factory=list)
    query_families: list[QueryFamily] = Field(default_factory=list)


class StrategyResult(BaseModel):
    """Typed result from the strategy-planning phase."""

    query: str
    complexity: str
    depth: ResearchDepth
    profile: QueryProfile
    strategy: StrategyPlan
    tasks_needed: list[str] = Field(default_factory=list)


class AnalysisFinding(BaseModel):
    """A single synthesized finding from the analysis phase."""

    title: str
    description: str = Field(default="")
    source: str | None = Field(default=None)
    evidence: list[str] = Field(default_factory=list)
    confidence: str | None = Field(default=None)


class AnalysisGap(BaseModel):
    """A coverage gap detected during analysis."""

    gap_description: str
    suggested_queries: list[str] = Field(default_factory=list)
    importance: str | None = Field(default=None)


class AnalysisResult(BaseModel):
    """Typed result from the analysis phase."""

    key_findings: list[AnalysisFinding | str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    themes_detailed: list[dict[str, Any]] = Field(default_factory=list)
    consensus_points: list[str] = Field(default_factory=list)
    contention_points: list[str] = Field(default_factory=list)
    cross_reference_claims: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[AnalysisGap | str] = Field(default_factory=list)
    source_count: int = Field(default=0, ge=0)
    analysis_method: str = Field(default="empty")
    deep_analysis_complete: bool = Field(default=False)
    analysis_passes: int = Field(default=0, ge=0)
    patterns: list[str] = Field(default_factory=list)
    disagreement_points: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    comprehensive_synthesis: str = Field(default="")

    model_config = {"extra": "allow"}

    def normalized_gaps(self) -> list[AnalysisGap]:
        """Return gaps in a consistent object form."""
        normalized: list[AnalysisGap] = []
        for gap in self.gaps:
            if isinstance(gap, AnalysisGap):
                normalized.append(gap)
            else:
                normalized.append(AnalysisGap(gap_description=str(gap)))
        return normalized

    def finding_sources(self) -> list[str]:
        """Return source references attached to findings when present."""
        sources: list[str] = []
        for finding in self.key_findings:
            if isinstance(finding, AnalysisFinding):
                if finding.source:
                    sources.append(finding.source)
                sources.extend(finding.evidence)
        return sources


class ValidationResult(BaseModel):
    """Typed result from the validation phase."""

    is_valid: bool = Field(default=False)
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    diversity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    content_depth_score: float = Field(default=0.0, ge=0.0, le=1.0)
    follow_up_queries: list[str] = Field(default_factory=list)
    needs_follow_up: bool = Field(default=False)
    target_source_count: int = Field(default=0, ge=0)


class IterationHistoryRecord(BaseModel):
    """One iteration of the iterative analysis workflow."""

    iteration: int = Field(ge=1)
    source_count: int = Field(default=0, ge=0)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    gap_count: int = Field(default=0, ge=0)
    follow_up_queries: list[str] = Field(default_factory=list)


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
