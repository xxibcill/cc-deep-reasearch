"""Analysis-domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .llm import LLMPlanModel
from .search import QueryFamily, QueryProfile, ResearchDepth
from .support import CrossReferenceClaim


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
    llm_plan: LLMPlanModel | None = Field(
        default=None,
        description="Per-agent LLM route plan from the planner",
    )


class AnalysisFinding(BaseModel):
    """A single synthesized finding from the analysis phase."""

    title: str
    summary: str = Field(
        default="",
        description="1-2 sentence high-level takeaway for Key Findings section",
    )
    description: str = Field(
        default="",
        description="Detailed explanation for Detailed Analysis section",
    )
    detail_points: list[str] = Field(
        default_factory=list,
        description="Evidence-backed detail bullets for Detailed Analysis",
    )
    source: str | None = Field(default=None)
    evidence: list[str] = Field(default_factory=list, description="Supporting source URLs")
    confidence: str | None = Field(default=None)
    claims: list[CrossReferenceClaim] = Field(default_factory=list)


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
    cross_reference_claims: list[CrossReferenceClaim] = Field(default_factory=list)
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


class IterationHistoryRecord(BaseModel):
    """One iteration of the iterative analysis workflow."""

    iteration: int = Field(ge=1)
    source_count: int = Field(default=0, ge=0)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    gap_count: int = Field(default=0, ge=0)
    follow_up_queries: list[str] = Field(default_factory=list)


__all__ = [
    "AnalysisFinding",
    "AnalysisGap",
    "AnalysisResult",
    "IterationHistoryRecord",
    "StrategyPlan",
    "StrategyResult",
    "ValidationResult",
]
