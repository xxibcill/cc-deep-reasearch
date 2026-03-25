"""Core models for the theme-based research system."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ResearchTheme(StrEnum):
    """Available research themes with tailored workflows."""

    GENERAL = "general"
    RESOURCES_GATHERING = "resources"
    TRIP_PLANNING = "trip_planning"
    BUSINESS_DUE_DILIGENCE = "due_diligence"
    MARKET_RESEARCH = "market_research"
    BUSINESS_IDEA_GENERATION = "business_ideas"
    CONTENT_CREATION = "content_creation"


class SourceRequirements(BaseModel):
    """Source requirements for a theme."""

    min_sources: int = Field(default=10, ge=1, description="Minimum sources to collect")
    preferred_source_types: list[str] = Field(
        default_factory=lambda: ["web"],
        description="Preferred source types (web, academic, official, news)",
    )
    prioritize_official_sources: bool = Field(
        default=False,
        description="Whether to prioritize official sources (e.g., government, company)",
    )
    credibility_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum credibility score for sources",
    )


class PhaseConfig(BaseModel):
    """Configuration for a single research phase."""

    enabled: bool = Field(default=True, description="Whether this phase is enabled")
    weight: float = Field(default=1.0, ge=0.0, le=2.0, description="Relative weight/importance")
    additional_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional parameters for this phase",
    )


class WorkflowConfig(BaseModel):
    """Complete workflow configuration for a research theme."""

    theme: ResearchTheme = Field(..., description="The theme this config applies to")
    display_name: str = Field(..., description="Human-readable theme name")
    description: str = Field(default="", description="Theme description")
    phases: list[str] = Field(
        default_factory=lambda: ["strategy", "expand", "collect", "analyze", "validate", "report"],
        description="Ordered list of phases to execute",
    )
    phase_configs: dict[str, PhaseConfig] = Field(
        default_factory=dict,
        description="Per-phase configuration overrides",
    )
    agent_configs: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-agent configuration overrides",
    )
    source_requirements: SourceRequirements = Field(
        default_factory=SourceRequirements,
        description="Source collection requirements",
    )
    output_template: str | None = Field(
        default=None,
        description="Optional output template name",
    )
    skip_deep_analysis: bool = Field(
        default=False,
        description="Whether to skip deep analysis phase",
    )
    skip_validation: bool = Field(
        default=False,
        description="Whether to skip validation phase",
    )
    enable_iterative_search: bool | None = Field(
        default=None,
        description="Override for iterative search setting",
    )

    def is_phase_enabled(self, phase_name: str) -> bool:
        """Check if a phase is enabled in this workflow."""
        config = self.phase_configs.get(phase_name)
        if config is None:
            return phase_name in self.phases
        return config.enabled

    def get_phase_weight(self, phase_name: str) -> float:
        """Get the weight for a phase."""
        config = self.phase_configs.get(phase_name)
        if config is None:
            return 1.0
        return config.weight


class DetectionResult(BaseModel):
    """Result of theme detection."""

    detected_theme: ResearchTheme = Field(..., description="The detected theme")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the detection",
    )
    matched_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns that matched for this theme",
    )
    all_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Scores for all themes considered",
    )

    def is_confident(self, threshold: float = 0.6) -> bool:
        """Check if detection confidence exceeds threshold."""
        return self.confidence >= threshold


__all__ = [
    "ResearchTheme",
    "SourceRequirements",
    "PhaseConfig",
    "WorkflowConfig",
    "DetectionResult",
]
