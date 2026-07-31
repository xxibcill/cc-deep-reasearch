"""Validated request contracts for content-generation API routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from cc_deep_research.content_gen.models.backlog import BacklogItem


class StartPipelineRequest(BaseModel):
    """Request body for starting a pipeline run."""

    theme: str = Field(min_length=1)
    from_stage: int = Field(default=0, ge=0)
    to_stage: int | None = Field(default=None, ge=0)
    content_type: str = ""
    effort_tier: Literal["quick", "standard", "deep"] = "standard"
    owner: str = ""
    channel_goal: str = ""
    success_target: str = ""
    research_depth_override: Literal["", "light", "standard", "deep"] = ""
    research_override_reason: str = ""


class ResumePipelineRequest(BaseModel):
    """Request body for resuming a pipeline run."""

    from_stage: int = Field(default=0, ge=0)


class ApproveQCRequest(BaseModel):
    """Request body for resolving QC with an explicit release state."""

    release_state: Literal["approved", "approved_with_known_risks"] = "approved"
    override_reason: str = ""
    actor: str = "operator"


class ApplyLearningsRequest(BaseModel):
    """Request body for promoting performance learnings into strategy rules."""

    learning_ids: list[str] = Field(default_factory=list)
    operator_approved: bool = True


class RunScriptingRequest(BaseModel):
    """Request body for standalone scripting runs."""

    idea: str = Field(min_length=1)
    iterative_mode: bool | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=5)
    llm_route: Literal["openrouter", "cerebras", "anthropic", "heuristic"] | None = Field(
        default=None
    )


class UpdateStrategyRequest(BaseModel):
    """Request body for updating strategy memory."""

    patch: dict[str, Any] = Field(default_factory=dict)


class UpdateBacklogItemRequest(BaseModel):
    """Request body for updating one backlog item."""

    patch: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# QC Issue request/response models
# ---------------------------------------------------------------------------


class CreateQCIssueRequest(BaseModel):
    """Request body for creating a QC issue."""

    category: str = Field(..., description="QCIssueCategory value")
    severity: str = Field(default="medium", description="QCIssueSeverity value")
    description: str = Field(..., min_length=1)
    affected_beat_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    idea_id: str = ""
    brief_id: str = ""
    stage_trace_id: str = ""
    publish_item_id: str = ""
    owner: str = ""


class UpdateQCIssueRequest(BaseModel):
    """Request body for updating a QC issue."""

    patch: dict[str, Any] = Field(default_factory=dict)


class ResolveQCIssueRequest(BaseModel):
    """Request body for resolving a QC issue."""

    resolution_note: str = Field(..., min_length=1)
    resolved_by: str = Field(default="operator")


# ---------------------------------------------------------------------------
# Publish queue operations request/response models
# ---------------------------------------------------------------------------


class UpdatePublishReadinessRequest(BaseModel):
    """Request body for updating publish queue item readiness."""

    readiness: str = Field(..., description="PublishReadinessState value")
    note: str = Field(default="")
    actor: str = Field(default="operator")


class AddPublishBlockerRequest(BaseModel):
    """Request body for adding a blocker to a publish queue item."""

    blocker_type: str = Field(
        ...,
        description="Blocker type: qc_issue, missing_asset, missing_approval, strategy_conflict",
    )
    description: str = Field(..., min_length=1)
    severity: str = Field(default="high")
    related_issue_ids: list[str] = Field(default_factory=list)
    related_asset_ids: list[str] = Field(default_factory=list)


class AddPublishNoteRequest(BaseModel):
    """Request body for adding an operator note to a publish queue item."""

    content: str = Field(..., min_length=1)
    author: str = Field(default="operator")


class AddPublishReviewEntryRequest(BaseModel):
    """Request body for adding a review entry to a publish queue item."""

    action: str = Field(..., min_length=1)
    actor: str = Field(default="operator")
    note: str = Field(default="")


# ---------------------------------------------------------------------------
# Reusable asset request/response models
# ---------------------------------------------------------------------------


class CreateReusableAssetRequest(BaseModel):
    """Request body for creating a reusable asset."""

    asset_type: str = Field(..., description="ReusableAssetType value")
    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    content: str = Field(default="")
    content_yaml: str = Field(default="")
    source_idea_id: str = ""
    source_run_id: str = ""
    source_brief_id: str = ""
    source_stage: str = ""
    extraction_reason: str = ""
    pillar: str = Field(default="")
    audience: str = Field(default="")
    platform: str = Field(default="")
    format: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchReusableAssetsRequest(BaseModel):
    """Request body for searching reusable assets."""

    query: str | None = None
    asset_type: str | None = None
    pillar: str | None = None
    audience: str | None = None
    platform: str | None = None
    format: str | None = None
    min_performance_score: float | None = None
    sort_by: str = Field(default="updated_at")
    sort_desc: bool = Field(default=True)


class CreateBacklogItemRequest(BaseModel):
    """Request body for creating a new backlog item."""

    title: str = ""
    one_line_summary: str = ""
    raw_idea: str = ""
    constraints: str = ""
    idea: str = ""
    category: str = ""
    audience: str = ""
    persona_detail: str = ""
    problem: str = ""
    emotional_driver: str = ""
    urgency_level: str = ""
    source: str = ""
    why_now: str = ""
    hook: str = ""
    content_type: str = ""
    format_duration: str = ""
    key_message: str = ""
    call_to_action: str = ""
    evidence: str = ""
    proof_gap_note: str = ""
    expertise_reason: str = ""
    genericity_risk: str = ""
    risk_level: str = "medium"
    source_theme: str = ""
    selection_reasoning: str = ""

    @model_validator(mode="after")
    def _require_title_or_idea(self) -> CreateBacklogItemRequest:
        if not (self.title or self.idea or self.raw_idea):
            raise ValueError("One of 'title', legacy 'idea', or 'raw_idea' is required")
        return self


class BacklogChatMessage(BaseModel):
    """A single message in the backlog chat conversation."""

    role: Literal["user", "assistant"]
    content: str


class BacklogChatOperationInput(BaseModel):
    """Operation proposed by the chat agent (used in apply request)."""

    kind: Literal["update_item", "create_item"]
    idea_id: str | None = None
    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class BacklogChatRespondRequest(BaseModel):
    """Request body for backlog-chat respond endpoint."""

    messages: list[BacklogChatMessage] = Field(default_factory=list)
    backlog_items: list[BacklogItem] = Field(default_factory=list)
    strategy: dict[str, Any] | None = None
    selected_idea_id: str | None = None
    mode: Literal["conversation", "edit"] = "edit"


class BacklogChatApplyRequest(BaseModel):
    """Request body for backlog-chat apply endpoint."""

    operations: list[BacklogChatOperationInput] = Field(default_factory=list)


class TriageOperationInput(BaseModel):
    """Triage operation proposed by the batch triage agent (used in apply request)."""

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
    preferred_idea_id: str | None = None


class TriageRespondRequest(BaseModel):
    """Request body for backlog-ai triage respond endpoint."""

    backlog_items: list[BacklogItem] = Field(default_factory=list)
    strategy: dict[str, Any] | None = None


class TriageApplyRequest(BaseModel):
    """Request body for backlog-ai triage apply endpoint."""

    operations: list[TriageOperationInput] = Field(default_factory=list)


class NextActionRequest(BaseModel):
    """Request body for next-action recommendation endpoint."""

    idea_id: str = Field(min_length=1)
    strategy: dict[str, Any] | None = None


class ExecutionBriefRequest(BaseModel):
    """Request body for execution brief generation endpoint."""

    idea_id: str = Field(min_length=1)
    strategy: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Brief management request / response models
# ---------------------------------------------------------------------------


class CreateBriefRequest(BaseModel):
    """Request body for creating a brief from an OpportunityBrief payload."""

    brief: dict[str, Any] = Field(..., description="OpportunityBrief fields as a dictionary")
    provenance: str = Field(default="generated")
    source_pipeline_id: str = Field(default="")
    revision_notes: str = Field(default="")


class SaveRevisionRequest(BaseModel):
    """Request body for saving a new revision of an existing brief."""

    brief: dict[str, Any] = Field(..., description="OpportunityBrief fields as a dictionary")
    revision_notes: str = Field(default="")
    source_pipeline_id: str = Field(default="")
    expected_updated_at: str | None = Field(
        default=None,
        description="Expected updated_at for optimistic concurrency. If provided and mismatched, returns 409.",
    )


class ApplyRevisionRequest(BaseModel):
    """Request body for applying a revision as the current head."""

    revision_id: str = Field(min_length=1, description="The revision_id to set as current head")
    expected_updated_at: str | None = Field(
        default=None,
        description="Expected updated_at for optimistic concurrency.",
    )


class UpdateBriefRequest(BaseModel):
    """Request body for updating brief metadata (title, etc.)."""

    patch: dict[str, Any] = Field(..., description="Fields to update")
    expected_updated_at: str | None = Field(
        default=None,
        description="Expected updated_at for optimistic concurrency.",
    )


class CloneBriefRequest(BaseModel):
    """Request body for cloning an existing brief."""

    new_title: str | None = Field(default=None, description="Optional new title for the clone")


class BriefAssistantMessage(BaseModel):
    """A single message in the brief assistant conversation."""

    role: Literal["user", "assistant"]
    content: str


class BriefAssistantProposalInput(BaseModel):
    """Proposal from the brief assistant (used in apply request)."""

    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class BriefAssistantRespondRequest(BaseModel):
    """Request body for brief-assistant respond endpoint."""

    messages: list[BriefAssistantMessage] = Field(default_factory=list)
    revision_id: str | None = Field(
        default=None, description="Specific revision to discuss (defaults to current head)"
    )
    mode: Literal["conversation", "edit"] = "edit"


class BriefAssistantApplyRequest(BaseModel):
    """Request body for brief-assistant apply endpoint."""

    proposals: list[BriefAssistantProposalInput] = Field(default_factory=list)
    revision_notes: str = Field(default="", description="Notes about what changed in this revision")
