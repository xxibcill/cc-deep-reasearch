"""Backlog stage models."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, model_validator


class IdeaCoreFields(BaseModel):
    """Identity and editorial framing for one backlog item."""

    category: Literal["", "trend-responsive", "evergreen", "authority-building"] = ""
    title: str = ""
    one_line_summary: str = ""
    raw_idea: str = ""
    constraints: str = ""
    source_theme: str = ""
    why_now: str = ""


class AudienceProblemFitFields(BaseModel):
    """Who the item targets and what tension it resolves."""

    audience: str = ""
    persona_detail: str = ""
    problem: str = ""
    emotional_driver: str = ""
    urgency_level: Literal["", "low", "medium", "high"] = ""


class ContentExecutionFields(BaseModel):
    """Fields that make the idea directly producible."""

    content_type: str = ""
    format_duration: str = ""
    hook: str = ""
    key_message: str = ""
    call_to_action: str = ""


class ValidationLayerFields(BaseModel):
    """Signals that determine whether the idea is credible and differentiated."""

    evidence: str = ""
    proof_gap_note: str = ""
    expertise_reason: str = ""
    genericity_risk: str = ""
    source: str = ""


class PrioritizationFields(BaseModel):
    """Selection and queueing metadata for backlog operations."""

    risk_level: Literal["low", "medium", "high"] = "medium"
    priority_score: float = 0.0
    impact_score: int | None = Field(default=None, ge=1, le=5)
    urgency_score: int | None = Field(default=None, ge=1, le=5)
    evidence_score: int | None = Field(default=None, ge=1, le=5)
    conversion_score: int | None = Field(default=None, ge=1, le=5)
    production_effort: int | None = Field(default=None, ge=1, le=5)
    latest_score: int | None = None
    latest_recommendation: Literal["", "produce_now", "hold", "kill"] = ""
    selection_reasoning: str = ""
    status: Literal["captured", "backlog", "selected", "archived"] = "backlog"
    production_status: Literal["idle", "in_production", "ready_to_publish"] = "idle"


class BacklogItem(
    IdeaCoreFields,
    AudienceProblemFitFields,
    ContentExecutionFields,
    ValidationLayerFields,
    PrioritizationFields,
):
    """Single backlog idea with scoring dimensions and legacy field compatibility.

    A single backlog idea scored across multiple dimensions.
    """

    idea_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    source_pipeline_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_scored_at: str = ""
    opportunity_brief_id: str = Field(
        default="",
        description="ID of the OpportunityBrief that this idea traces back to",
    )
    persona_detail: str = ""
    # Rejection tracking
    is_rejected: bool = False
    rejection_reason: str = ""
    # Legacy content type (used if content_type is empty)
    content_format: str = ""
    # Additional metadata
    source_url: str = ""
    # Shortlist selection
    shortlist_rank: int | None = None  # None = not shortlisted
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

    def __getattr__(self, name: str) -> Any:
        """Provide legacy field accessors for backward compatibility."""
        if name == "idea":
            return self.title
        if name == "potential_hook":
            return self.hook
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "idea":
            object.__setattr__(self, "title", value)
            return
        if name == "potential_hook":
            object.__setattr__(self, "hook", value)
            return
        super().__setattr__(name, value)

    @computed_field(return_type=str)
    @property
    def idea(self) -> str:
        """Legacy serialized alias for title."""
        return self.title

    @computed_field(return_type=str)
    @property
    def potential_hook(self) -> str:
        """Legacy serialized alias for hook."""
        return self.hook

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
        legacy_status = str(data.get("status") or "").strip()
        if not data.get("production_status"):
            if legacy_status == "in_production":
                data["production_status"] = "in_production"
            elif legacy_status == "published":
                data["production_status"] = "ready_to_publish"
        if legacy_status in {"runner_up", "in_production", "published"}:
            data["status"] = "backlog"
        component_keys = (
            "impact_score",
            "urgency_score",
            "evidence_score",
            "conversion_score",
            "production_effort",
        )
        if not data.get("priority_score") and all(data.get(key) is not None for key in component_keys):
            effort_score = max(1, min(5, 6 - int(data["production_effort"])))
            weighted = (
                int(data["impact_score"]) * 0.30
                + int(data["urgency_score"]) * 0.20
                + int(data["evidence_score"]) * 0.20
                + int(data["conversion_score"]) * 0.20
                + effort_score * 0.10
            )
            data["priority_score"] = round((weighted / 5) * 100, 1)
        return data

    @model_validator(mode="after")
    def _sync_legacy_fields(self) -> BacklogItem:
        canonical_title = self.title.strip() or self.one_line_summary.strip()
        canonical_summary = self.one_line_summary.strip() or canonical_title
        canonical_hook = self.hook.strip()
        self.title = canonical_title
        self.one_line_summary = canonical_summary
        self.hook = canonical_hook
        if self.status == "captured" and self.title.strip():
            self.status = "backlog"
        if self.status == "backlog" and self.raw_idea.strip() and not self.title.strip():
            self.status = "captured"
        return self


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
