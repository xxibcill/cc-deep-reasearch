"""Session-domain models and metadata normalization."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .search import ResearchDepth, SearchResult, SearchResultItem


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


class SessionPromptMetadata(BaseModel):
    """Stable prompt configuration metadata for a research session.

    Attributes:
        overrides_applied: Whether any prompt overrides were applied.
        effective_overrides: Dictionary of agent_id -> {system_prompt, prompt_prefix}.
        default_prompts_used: List of agents using default prompts.
    """

    overrides_applied: bool = Field(default=False)
    effective_overrides: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    default_prompts_used: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class SessionMetadataContract(BaseModel):
    """Stable top-level shape for ``ResearchSession.metadata``."""

    strategy: dict[str, Any] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    iteration_history: list[dict[str, Any]] = Field(default_factory=list)
    providers: SessionProvidersMetadata = Field(default_factory=SessionProvidersMetadata)
    execution: SessionExecutionMetadata = Field(default_factory=SessionExecutionMetadata)
    deep_analysis: SessionDeepAnalysisMetadata = Field(
        default_factory=SessionDeepAnalysisMetadata
    )
    llm_routes: dict[str, Any] = Field(default_factory=dict)
    prompts: SessionPromptMetadata = Field(default_factory=SessionPromptMetadata)

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
    depth: ResearchDepth,
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


def _build_prompt_metadata(
    raw_metadata: Mapping[str, Any],
) -> SessionPromptMetadata:
    """Normalize prompt metadata from legacy or explicit payloads."""
    raw_prompts = raw_metadata.get("prompts", {})
    if isinstance(raw_prompts, SessionPromptMetadata):
        return raw_prompts

    if not isinstance(raw_prompts, dict):
        return SessionPromptMetadata()

    effective_overrides: dict[str, dict[str, str | None]] = {}
    raw_overrides = raw_prompts.get("effective_overrides", {})
    if isinstance(raw_overrides, dict):
        for agent_id, override in raw_overrides.items():
            if isinstance(override, dict):
                effective_overrides[agent_id] = {
                    "system_prompt": override.get("system_prompt"),
                    "prompt_prefix": override.get("prompt_prefix"),
                }

    default_prompts_used = _list_of_strings(raw_prompts.get("default_prompts_used", []))

    return SessionPromptMetadata(
        overrides_applied=bool(raw_prompts.get("overrides_applied", False)),
        effective_overrides=effective_overrides,
        default_prompts_used=default_prompts_used,
    )


def normalize_session_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    depth: ResearchDepth,
    configured_providers: list[str] | None = None,
) -> dict[str, Any]:
    """Return a stable metadata contract for a research session."""
    raw_metadata = dict(metadata or {})
    configured = list(configured_providers or [])
    analysis = _mapping_dict(raw_metadata.get("analysis", {}))
    providers = _build_provider_metadata(raw_metadata, configured)
    deep_analysis = _build_deep_analysis_metadata(raw_metadata, depth, analysis)
    prompt_metadata = _build_prompt_metadata(raw_metadata)

    raw_execution = _mapping_dict(raw_metadata.get("execution", {}))
    degraded_reasons = _list_of_strings(raw_execution.get("degraded_reasons", []))
    if providers.status != ProviderStatus.READY:
        degraded_reasons.extend(providers.warnings)
    if deep_analysis.status == DeepAnalysisStatus.DEGRADED and deep_analysis.reason:
        degraded_reasons.append(deep_analysis.reason)
    degraded_reasons = list(dict.fromkeys(degraded_reasons))

    contract = SessionMetadataContract(
        strategy=dict(_mapping_dict(raw_metadata.get("strategy", {}))),
        analysis=dict(analysis),
        validation=dict(_mapping_dict(raw_metadata.get("validation", {}))),
        iteration_history=[
            dict(_mapping_dict(item))
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
        prompts=prompt_metadata,
    )
    return contract.model_dump(mode="python")


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


__all__ = [
    "DeepAnalysisStatus",
    "ProviderStatus",
    "ResearchSession",
    "SessionDeepAnalysisMetadata",
    "SessionExecutionMetadata",
    "SessionMetadataContract",
    "SessionPromptMetadata",
    "SessionProvidersMetadata",
    "normalize_session_metadata",
]
