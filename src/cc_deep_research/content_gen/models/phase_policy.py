"""Operating-phase governance model definitions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .shared import OperatingPhase


class PhaseExitCriteria(BaseModel):
    """Exit criteria for completing a phase."""

    description: str = Field(
        default="", description="Human-readable description of what constitutes phase completion."
    )
    required_artifacts: list[str] = Field(
        default_factory=list,
        description="List of artifact names that must be present to exit the phase.",
    )
    quality_threshold: float | None = Field(
        default=None, description="Optional quality score threshold to meet before exiting."
    )


class PhaseSkipCondition(BaseModel):
    """Condition under which a phase can be skipped."""

    reason: str = Field(
        default="", description="Human-readable reason why the phase can be skipped."
    )
    requires_manual_override: bool = Field(
        default=False, description="Whether operator confirmation is required to skip."
    )
    preserves_quality: bool = Field(
        default=True, description="Whether skipping this phase preserves output quality."
    )


class PhaseKillCondition(BaseModel):
    """Condition under which a phase should be terminated early."""

    reason: str = Field(
        default="", description="Human-readable reason why the phase should be killed."
    )
    abort_pipeline: bool = Field(
        default=False, description="Whether killing this phase should abort the entire pipeline."
    )
    preserve_artifacts: bool = Field(
        default=True, description="Whether to preserve partial artifacts even when killed."
    )


class PhaseReuseOpportunity(BaseModel):
    """Opportunity to reuse phase outputs across runs."""

    description: str = Field(default="", description="What can be reused from this phase.")
    reuse_pattern: str = Field(
        default="", description="How to reuse (e.g., 'cache', 'template', 'reference')."
    )
    ttl_hours: int | None = Field(
        default=None, description="How long reuse is valid (None = until next strategy update)."
    )


class OperatingPhasePolicy(BaseModel):
    """Typed governance metadata for one operating phase."""

    phase: OperatingPhase = Field(description="Which operating phase this policy governs.")
    phase_label: str = Field(description="Human-readable phase name.")
    owner: str = Field(default="", description="Who is responsible for this phase (role or team).")
    max_turnaround_minutes: int = Field(
        default=60, description="Expected maximum turnaround time for this phase in minutes."
    )
    entry_criteria: list[str] = Field(
        default_factory=list,
        description="List of conditions that must be true before phase execution.",
    )
    exit_criteria: PhaseExitCriteria = Field(
        default_factory=PhaseExitCriteria,
        description="Criteria for successfully completing this phase.",
    )
    skip_conditions: list[PhaseSkipCondition] = Field(
        default_factory=list, description="Conditions under which this phase can be skipped."
    )
    kill_conditions: list[PhaseKillCondition] = Field(
        default_factory=list, description="Conditions under which this phase should be killed."
    )
    reuse_opportunities: list[PhaseReuseOpportunity] = Field(
        default_factory=list, description="Opportunities to reuse phase outputs in future runs."
    )


__all__ = [
    "OperatingPhasePolicy",
    "PhaseExitCriteria",
    "PhaseKillCondition",
    "PhaseReuseOpportunity",
    "PhaseSkipCondition",
]
