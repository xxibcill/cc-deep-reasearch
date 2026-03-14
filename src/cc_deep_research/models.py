"""Core data structures for CC Deep Research CLI."""

from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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
    llm_plan: "LLMPlanModel | None" = Field(
        default=None,
        description="Per-agent LLM route plan from the planner",
    )


class AnalysisFinding(BaseModel):
    """A single synthesized finding from the analysis phase.

    This model separates high-level summary from detailed analysis to enable
    cleaner report rendering with distinct Key Findings and Detailed Analysis sections.
    """

    title: str
    summary: str = Field(default="", description="1-2 sentence high-level takeaway for Key Findings section")
    description: str = Field(default="", description="Detailed explanation for Detailed Analysis section")
    detail_points: list[str] = Field(default_factory=list, description="Evidence-backed detail bullets for Detailed Analysis")
    source: str | None = Field(default=None)
    evidence: list[str] = Field(default_factory=list, description="Supporting source URLs")
    confidence: str | None = Field(default=None)
    claims: list["CrossReferenceClaim"] = Field(default_factory=list)


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
    cross_reference_claims: list["CrossReferenceClaim"] = Field(default_factory=list)
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
    failure_modes: list[str] = Field(default_factory=list)
    evidence_diagnosis: str = Field(default="unknown")
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    diversity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    content_depth_score: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness_fitness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    primary_source_coverage_score: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_support_density_score: float = Field(default=0.0, ge=0.0, le=1.0)
    contradiction_pressure_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_type_diversity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    follow_up_queries: list[str] = Field(default_factory=list)
    needs_follow_up: bool = Field(default=False)
    target_source_count: int = Field(default=0, ge=0)


class ReportEvaluationResult(BaseModel):
    """Typed result from report quality evaluation phase.

    This evaluates FINAL markdown report content for:
    - Writing quality (clarity, grammar, coherence)
    - Report structure and flow
    - Technical accuracy of synthesized content
    - User experience (readability, usefulness)
    - Consistency with analysis findings
    """

    # Overall assessment
    overall_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_acceptable: bool = Field(default=False)

    # Dimension scores (0-1 each)
    writing_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    structure_flow_score: float = Field(default=0.0, ge=0.0, le=1.0)
    technical_accuracy_score: float = Field(default=0.0, ge=0.0, le=1.0)
    user_experience_score: float = Field(default=0.0, ge=0.0, le=1.0)
    consistency_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Issues and recommendations
    critical_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    # Detailed assessment
    dimension_assessments: dict[str, Any] = Field(default_factory=dict)
    evaluation_method: str = Field(default="llm_analysis")


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
    llm_routes: dict[str, Any] = Field(default_factory=dict)

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
    ``providers``, ``execution``, ``deep_analysis``, and ``llm_routes``.
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
        llm_routes=_mapping_dict(raw_metadata.get("llm_routes", {})),
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


class LLMTransportType(StrEnum):
    """Transport mechanism for LLM operations."""

    CLAUDE_CLI = "claude_cli"
    OPENROUTER_API = "openrouter_api"
    CEREBRAS_API = "cerebras_api"
    HEURISTIC = "heuristic"


class LLMProviderType(StrEnum):
    """LLM provider identifier."""

    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    CEREBRAS = "cerebras"
    HEURISTIC = "heuristic"


class LLMRouteModel(BaseModel):
    """Route configuration for a single LLM transport.

    This model is used in strategy output to specify which LLM
    route an agent should use for its operations.
    """

    transport: LLMTransportType = Field(
        default=LLMTransportType.CLAUDE_CLI,
        description="Transport mechanism for this route",
    )
    provider: LLMProviderType = Field(
        default=LLMProviderType.CLAUDE,
        description="LLM provider for this route",
    )
    model: str = Field(
        default="claude-sonnet-4-6",
        description="Model identifier for the provider",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this route is available for use",
    )


class LLMPlanModel(BaseModel):
    """Per-agent LLM route plan from strategy output.

    The planner emits this model to specify which LLM route each
    agent should use during the research session.
    """

    agent_routes: dict[str, LLMRouteModel] = Field(
        default_factory=dict,
        description="Mapping from agent ID to its assigned route",
    )
    fallback_order: list[LLMTransportType] = Field(
        default_factory=lambda: [
            LLMTransportType.CLAUDE_CLI,
            LLMTransportType.OPENROUTER_API,
            LLMTransportType.CEREBRAS_API,
            LLMTransportType.HEURISTIC,
        ],
        description="Ordered list of fallback transports",
    )
    default_route: LLMRouteModel = Field(
        default_factory=LLMRouteModel,
        description="Default route for agents without explicit assignment",
    )

    def get_route_for_agent(self, agent_id: str) -> LLMRouteModel:
        """Get the route for a specific agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            The assigned route or the default route if not explicitly assigned.
        """
        return self.agent_routes.get(agent_id, self.default_route)


class QualityScore(BaseModel):
    """Quality score for a source."""

    credibility: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness: float = Field(default=0.5, ge=0.0, le=1.0)
    diversity: float = Field(default=0.5, ge=0.0, le=1.0)
    overall: float = Field(default=0.5, ge=0.0, le=1.0)


class EvidenceType(StrEnum):
    """High-level classification for evidence attached to a claim."""

    PRIMARY = "primary"
    RESEARCH = "research"
    NEWS = "news"
    OFFICIAL = "official"
    SECONDARY = "secondary"
    UNKNOWN = "unknown"


class ClaimFreshness(StrEnum):
    """Freshness bucket for evidence or claims."""

    CURRENT = "current"
    RECENT = "recent"
    DATED = "dated"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    """Enhanced source classification for quality assessment."""

    PRIMARY_RESEARCH = "primary_research"
    PREPRINT = "preprint"
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    MEDICAL_REFERENCE = "medical_reference"
    COMMERCIAL_BLOG = "commercial_blog"
    OFFICIAL_DOCUMENT = "official_document"
    PROTOCOL_DOCUMENT = "protocol_document"
    GENERAL_WEB = "general_web"


class ResearchGapType(str):
    """Types of research gaps that can be automatically detected."""

    MISSING_QUANTITATIVE_DATA = "missing_quantitative_data"
    MISSING_COMPARATIVE_STUDIES = "missing_comparative_studies"
    MISSING_MECHANISM_DETAILS = "missing_mechanism_details"
    MISSING_SAFETY_DATA = "missing_safety_data"
    MISSING_CLINICAL_TRIALS = "missing_clinical_trials"
    MISSING_LONGITUDINAL_DATA = "missing_longitudinal_data"


def _parse_published_date(value: Any) -> datetime | None:
    """Parse loose publication dates from source metadata."""
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _classify_claim_freshness(value: Any) -> ClaimFreshness:
    """Map a publication date into coarse freshness buckets."""
    published_at = _parse_published_date(value)
    if published_at is None:
        return ClaimFreshness.UNKNOWN

    age_days = max(0, (datetime.utcnow() - published_at).days)
    if age_days <= 30:
        return ClaimFreshness.CURRENT
    if age_days <= 365:
        return ClaimFreshness.RECENT
    return ClaimFreshness.DATED


def _infer_evidence_type(
    *,
    url: str,
    title: str,
    metadata: Mapping[str, Any],
    query_provenance: list[QueryProvenance],
) -> EvidenceType:
    """Infer an evidence class from stable source signals."""
    haystack = " ".join(
        [
            url.lower(),
            title.lower(),
            " ".join(str(tag).lower() for tag in metadata.get("query_intent_tags", [])),
            " ".join(entry.family.lower() for entry in query_provenance),
            " ".join(tag.lower() for entry in query_provenance for tag in entry.intent_tags),
        ]
    )

    if any(token in haystack for token in ("pubmed", "doi.org", "journal", "clinical trial")):
        return EvidenceType.RESEARCH
    if any(token in haystack for token in (".gov", ".edu", "sec.", "fda", "cdc", "who.int")):
        return EvidenceType.OFFICIAL
    if any(token in haystack for token in ("reuters", "apnews", "bloomberg", "nytimes", "news")):
        return EvidenceType.NEWS
    if any(token in haystack for token in ("primary-source", "evidence", "filing", "transcript")):
        return EvidenceType.PRIMARY
    if any(token in haystack for token in ("wikipedia", "blog", "review", "summary")):
        return EvidenceType.SECONDARY
    return EvidenceType.UNKNOWN


class ClaimEvidence(BaseModel):
    """One source item attached to a supporting or contradicting claim."""

    url: str = Field(..., min_length=1)
    title: str = Field(default="")
    snippet: str = Field(default="")
    published_date: str | None = Field(default=None)
    query_provenance: list[QueryProvenance] = Field(default_factory=list)
    freshness: ClaimFreshness = Field(default=ClaimFreshness.UNKNOWN)
    evidence_type: EvidenceType = Field(default=EvidenceType.UNKNOWN)
    source_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_source_shapes(cls, value: Any) -> Any:
        """Accept URLs, source models, and raw dictionaries."""
        if isinstance(value, ClaimEvidence):
            return value
        if isinstance(value, str):
            return {"url": value}
        if isinstance(value, SearchResultItem):
            return {
                "url": value.url,
                "title": value.title,
                "snippet": value.snippet or value.content or "",
                "published_date": (
                    value.source_metadata.get("published_date")
                    or value.source_metadata.get("published")
                ),
                "query_provenance": [
                    entry.model_dump(mode="python") for entry in value.query_provenance
                ],
                "source_metadata": dict(value.source_metadata),
            }
        if isinstance(value, Mapping):
            payload = dict(value)
            if "source_url" in payload and "url" not in payload:
                payload["url"] = payload["source_url"]
            if "metadata" in payload and "source_metadata" not in payload:
                metadata = payload.get("metadata")
                payload["source_metadata"] = dict(metadata) if isinstance(metadata, Mapping) else {}
            return payload
        return value

    @model_validator(mode="after")
    def _normalize_metadata(self) -> "ClaimEvidence":
        """Synchronize provenance, freshness, and evidence typing."""
        metadata = dict(self.source_metadata)
        provenance = _normalize_query_provenance_entries(self.query_provenance)
        if not provenance:
            provenance = _normalize_query_provenance_entries(metadata.get("query_provenance"))
        self.query_provenance = provenance

        if self.published_date is None:
            self.published_date = metadata.get("published_date") or metadata.get("published")
        if self.freshness == ClaimFreshness.UNKNOWN:
            self.freshness = _classify_claim_freshness(self.published_date)
        if self.evidence_type == EvidenceType.UNKNOWN:
            self.evidence_type = _infer_evidence_type(
                url=self.url,
                title=self.title,
                metadata=metadata,
                query_provenance=provenance,
            )

        metadata["query_provenance"] = [
            entry.model_dump(mode="python") for entry in self.query_provenance
        ]
        if self.published_date:
            metadata["published_date"] = self.published_date
        metadata["freshness"] = self.freshness.value
        metadata["evidence_type"] = self.evidence_type.value
        self.source_metadata = metadata
        return self


def _normalize_claim_evidence_entries(value: Any) -> list[ClaimEvidence]:
    """Coerce mixed evidence payloads into typed evidence entries."""
    if isinstance(value, list):
        raw_entries = value
    elif value is None:
        raw_entries = []
    else:
        raw_entries = [value]

    normalized: list[ClaimEvidence] = []
    seen: set[str] = set()
    for entry in raw_entries:
        try:
            evidence = ClaimEvidence.model_validate(entry)
        except Exception:
            continue
        if evidence.url in seen:
            continue
        seen.add(evidence.url)
        normalized.append(evidence)
    return normalized


def _derive_claim_freshness(evidence: list[ClaimEvidence]) -> ClaimFreshness:
    """Derive a claim freshness rating from attached evidence."""
    if not evidence:
        return ClaimFreshness.UNKNOWN
    if any(item.freshness == ClaimFreshness.CURRENT for item in evidence):
        return ClaimFreshness.CURRENT
    if any(item.freshness == ClaimFreshness.RECENT for item in evidence):
        return ClaimFreshness.RECENT
    if any(item.freshness == ClaimFreshness.DATED for item in evidence):
        return ClaimFreshness.DATED
    return ClaimFreshness.UNKNOWN


def _derive_claim_evidence_type(evidence: list[ClaimEvidence]) -> EvidenceType:
    """Select the dominant evidence type across supporting evidence."""
    types = [item.evidence_type for item in evidence if item.evidence_type != EvidenceType.UNKNOWN]
    if not types:
        return EvidenceType.UNKNOWN
    return Counter(types).most_common(1)[0][0]


def _derive_claim_confidence(
    support_count: int,
    contradiction_count: int,
    consensus_level: float,
) -> str:
    """Infer a coarse confidence level from support and contradiction counts."""
    if support_count >= 3 and contradiction_count == 0 and consensus_level >= 0.6:
        return "high"
    if support_count >= 2 and contradiction_count <= 1:
        return "medium"
    return "low"


class CrossReferenceClaim(BaseModel):
    """A claim found across multiple sources."""

    claim: str
    supporting_sources: list[ClaimEvidence] = Field(default_factory=list)
    contradicting_sources: list[ClaimEvidence] = Field(default_factory=list)
    confidence: str | None = Field(default=None)
    freshness: ClaimFreshness | None = Field(default=None)
    evidence_type: EvidenceType | None = Field(default=None)
    consensus_level: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("supporting_sources", "contradicting_sources", mode="before")
    @classmethod
    def _normalize_sources(cls, value: Any) -> list[ClaimEvidence]:
        """Accept legacy URL lists and normalize them to claim evidence."""
        return _normalize_claim_evidence_entries(value)

    @model_validator(mode="after")
    def _derive_metadata(self) -> "CrossReferenceClaim":
        """Fill derived claim metadata from attached evidence."""
        if self.freshness is None:
            self.freshness = _derive_claim_freshness(self.supporting_sources)
        if self.evidence_type is None:
            self.evidence_type = _derive_claim_evidence_type(self.supporting_sources)
        if self.confidence is None:
            self.confidence = _derive_claim_confidence(
                support_count=len(self.supporting_sources),
                contradiction_count=len(self.contradicting_sources),
                consensus_level=self.consensus_level,
            )
        return self
