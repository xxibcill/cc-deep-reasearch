"""Typed metadata contracts for session persistence."""

from __future__ import annotations

from typing import Any, NotRequired

from typing_extensions import TypedDict


class StrategyMetadataContract(TypedDict, total=False):
    """Persisted shape for strategy metadata."""

    query: str
    complexity: str
    depth: str
    profile: dict[str, Any]
    strategy: dict[str, Any]
    tasks_needed: list[str]
    llm_plan: dict[str, Any] | None


class AnalysisMetadataContract(TypedDict, total=False):
    """Persisted shape for analysis metadata."""

    key_findings: list[Any]
    themes: list[str]
    themes_detailed: list[dict[str, Any]]
    consensus_points: list[str]
    contention_points: list[str]
    cross_reference_claims: list[dict[str, Any]]
    gaps: list[Any]
    source_count: int
    analysis_method: str
    deep_analysis_complete: bool
    analysis_passes: int
    patterns: list[str]
    disagreement_points: list[str]
    implications: list[str]
    comprehensive_synthesis: str
    source_provenance: dict[str, Any]


class ValidationMetadataContract(TypedDict, total=False):
    """Persisted shape for validation metadata."""

    is_valid: bool
    issues: list[str]
    warnings: list[str]
    recommendations: list[str]
    failure_modes: list[str]
    evidence_diagnosis: str
    quality_score: float
    diversity_score: float
    content_depth_score: float
    freshness_fitness_score: float
    primary_source_coverage_score: float
    claim_support_density_score: float
    contradiction_pressure_score: float
    source_type_diversity_score: float
    follow_up_queries: list[str]
    needs_follow_up: bool
    target_source_count: int


class IterationHistoryEntryContract(TypedDict, total=False):
    """Persisted shape for iteration history entries."""

    iteration: int
    source_count: int
    quality_score: float | None
    gap_count: int
    follow_up_queries: list[str]
    current_hypothesis: str
    planner_summary: str
    stop_reason: str | None


__all__ = [
    "AnalysisMetadataContract",
    "IterationHistoryEntryContract",
    "StrategyMetadataContract",
    "ValidationMetadataContract",
]
