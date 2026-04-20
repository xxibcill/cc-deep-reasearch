"""Backlog stage models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class IdeaCoreFields(BaseModel):
    """Core idea fields used in backlog scoring."""

    title: str = ""
    one_line_summary: str = ""
    category: str = ""
    audience: str = ""
    problem: str = ""
    why_now: str = ""
    hook: str = ""
    content_type: str = ""
    key_message: str = ""
    call_to_action: str = ""
    evidence: str = ""
    risk_level: str = ""


class AudienceProblemFitFields(BaseModel):
    """Audience and problem fit dimensions for scoring."""

    audience_match: float = 0.0
    problem_clarity: float = 0.0
    timeliness_relevance: float = 0.0
    emotional_resonance: float = 0.0


class ContentExecutionFields(BaseModel):
    """Content execution dimensions for scoring."""

    production_ease: float = 0.0
    evidence_strength: float = 0.0
    hook_strength: float = 0.0
    structure_fit: float = 0.0
    differentiation: float = 0.0


class ValidationLayerFields(BaseModel):
    """Validation layer dimensions for scoring."""

    safety_check: float = 0.0
    claim_verifiability: float = 0.0
    legal_risk: float = 0.0


class PrioritizationFields(BaseModel):
    """Final prioritization fields."""

    total_score: float = 0.0
    recommendation: str = ""
    reason: str = ""


class BacklogItem(
    IdeaCoreFields,
    AudienceProblemFitFields,
    ContentExecutionFields,
    ValidationLayerFields,
    PrioritizationFields,
):
    """Single backlog idea with scoring dimensions (spec stage 3).

    A single backlog idea scored across multiple dimensions.
    """

    idea_id: str = Field(description="Unique idea identifier")
    persona_detail: str = ""
    # Rejection tracking
    is_rejected: bool = False
    rejection_reason: str = ""
    # Legacy content type (used if content_type is empty)
    content_format: str = ""
    # Additional metadata
    source: str = ""
    source_url: str = ""

    # Shortlist selection
    shortlist_rank: int | None = None  # None = not shortlisted

    # P3-T3: Generic framing / undifferentiated content detection
    genericity_flags: list[str] = Field(
        default_factory=list,
        description="Specific framings that sound like everyone else",
    )
    interchangeability_warnings: list[str] = Field(
        default_factory=list,
        description="Claims or angles that are interchangeable with competitors",
    )

    def is_shortlisted(self) -> bool:
        """Return True if this idea is on the shortlist."""
        return self.shortlist_rank is not None

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, raw: Any) -> Any:
        """Normalize legacy field names for backward compatibility."""
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        # Handle legacy field names (map to current canonical names)
        if data.get("idea") and "title" not in data:
            data["title"] = str(data["idea"])
        if data.get("potential_hook") and "hook" not in data:
            data["hook"] = str(data["potential_hook"])
        return data


class BacklogOutput(BaseModel):
    """Output of the backlog builder stage."""

    items: list[BacklogItem] = Field(default_factory=list)
    rejected_count: int = 0
    rejection_reasons: list[str] = Field(default_factory=list)
    is_degraded: bool = False
    degradation_reason: str = ""

    # Alias for backward compat
    @property
    def ideas(self) -> list[BacklogItem]:
        return self.items


class IdeaScores(BaseModel):
    """Per-idea score breakdown."""

    idea_id: str
    relevance: float = 0.0
    novelty: float = 0.0
    authority_fit: float = 0.0
    production_ease: float = 0.0
    evidence_strength: float = 0.0
    hook_strength: float = 0.0
    repurposing: float = 0.0
    total_score: float = 0.0
    recommendation: str = ""
    reason: str = ""


class ScoringOutput(BaseModel):
    """Output of the idea scoring stage."""

    scores: list[IdeaScores] = Field(default_factory=list)
    shortlist: list[str] = Field(
        default_factory=list,
        description="Idea IDs shortlisted for production",
    )
    selected_idea_id: str = Field(
        default="",
        description="The single idea selected for production",
    )
    runner_up_idea_ids: list[str] = Field(default_factory=list)
    selection_reasoning: str = ""
    active_candidates: list[BacklogItem] = Field(default_factory=list)


class TriageOperation(BaseModel):
    """A single triage operation proposed by the batch triage agent."""

    kind: Literal[
        "batch_enrich",
        "batch_reframe",
        "dedupe_recommendation",
        "archive_recommendation",
        "priority_recommendation",
    ]
    idea_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    preferred_idea_id: str | None = None  # for dedupe: which item to keep


class PipelineCandidate(BaseModel):
    """One active candidate lane in the small editorial queue."""

    idea_id: str
    role: Literal["primary", "runner_up"] = "primary"
    status: Literal["selected", "runner_up", "in_production", "published"] = "selected"
    content_type_profile: str = Field(
        default="",
        description="Profile key for branching decisions in this lane",
    )


class TriageResponse(BaseModel):
    """Structured response from the batch triage agent."""

    reply_markdown: str
    proposals: list[TriageOperation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    mentioned_idea_ids: list[str] = Field(default_factory=list)
