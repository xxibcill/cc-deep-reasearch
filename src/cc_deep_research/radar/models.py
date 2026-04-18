"""Domain models for Opportunity Radar.

These models define the canonical schema for Radar entities:
- RadarSource: a monitored source definition
- RawSignal: a normalized, auditable source item before clustering
- Opportunity: a structured, decision-ready candidate shown to the user
- OpportunityScore: scoring breakdown and explanation for an opportunity
- OpportunitySignalLink: many-to-many join between opportunities and raw signals
- OpportunityFeedback: user response events to opportunities
- WorkflowLink: connects opportunities to downstream workflow objects
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceType(StrEnum):
    """Types of sources that Radar can monitor."""

    NEWS = "news"
    BLOG = "blog"
    CHANGELOG = "changelog"
    FORUM = "forum"
    SOCIAL = "social"
    COMPETITOR = "competitor"
    CUSTOM = "custom"


class SourceStatus(StrEnum):
    """Active state of a Radar source."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class OpportunityType(StrEnum):
    """Types of opportunities detected by Radar."""

    COMPETITOR_MOVE = "competitor_move"
    AUDIENCE_QUESTION = "audience_question"
    RISING_TOPIC = "rising_topic"
    NARRATIVE_SHIFT = "narrative_shift"
    LAUNCH_UPDATE_CHANGE = "launch_update_change"
    PROOF_POINT = "proof_point"
    RECURRING_PATTERN = "recurring_pattern"


class OpportunityStatus(StrEnum):
    """Lifecycle status of an opportunity."""

    NEW = "new"
    SAVED = "saved"
    ACTED_ON = "acted_on"
    MONITORING = "monitoring"
    DISMISSED = "dismissed"
    ARCHIVED = "archived"


class FreshnessState(StrEnum):
    """Freshness indicator for an opportunity."""

    NEW = "new"
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"


class PriorityLabel(StrEnum):
    """User-facing priority labels derived from score bands."""

    ACT_NOW = "act_now"
    HIGH_POTENTIAL = "high_potential"
    MONITOR = "monitor"
    LOW_PRIORITY = "low_priority"


class FeedbackType(StrEnum):
    """Explicit feedback actions a user can take on an opportunity."""

    ACTED_ON = "acted_on"
    SAVED = "saved"
    DISMISSED = "dismissed"
    IGNORED = "ignored"
    CONVERTED_TO_RESEARCH = "converted_to_research"
    CONVERTED_TO_CONTENT = "converted_to_content"


class WorkflowType(StrEnum):
    """Downstream workflow types that an opportunity can convert to."""

    RESEARCH_RUN = "research_run"
    BRIEF = "brief"
    BACKLOG_ITEM = "backlog_item"
    CONTENT_PIPELINE = "content_pipeline"


# ---------------------------------------------------------------------------
# Persistence Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(tz=UTC).isoformat()


def _generate_id(prefix: str = "") -> str:
    """Generate a unique identifier with optional prefix."""
    uid = uuid4().hex[:12]
    return f"{prefix}-{uid}" if prefix else uid


# ---------------------------------------------------------------------------
# RadarSource
# ---------------------------------------------------------------------------


class RadarSource(BaseModel):
    """Represents a monitored source definition.

    A source defines what Radar watches (e.g., a competitor blog, industry news).

    Attributes:
        id: Unique identifier for this source.
        source_type: Category of the source (news, blog, changelog, etc.).
        label: Human-readable label for display in the UI.
        url_or_identifier: URL, RSS feed, or other identifier for the source.
        status: Whether the source is actively monitored.
        scan_cadence: How often to scan this source (e.g., "1h", "6h", "1d").
        last_scanned_at: ISO timestamp of the last scan attempt.
        created_at: When this source was added.
        updated_at: When this source was last modified.
        metadata: Additional source-specific configuration.
    """

    id: str = Field(default_factory=lambda: _generate_id("src"))
    source_type: SourceType
    label: str
    url_or_identifier: str
    status: SourceStatus = SourceStatus.ACTIVE
    scan_cadence: str = "6h"
    last_scanned_at: str | None = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("updated_at", mode="after")
    @classmethod
    def _touch_updated_at(cls, _: Any) -> str:
        """Update the updated_at timestamp on every serialization."""
        return _now_iso()


# ---------------------------------------------------------------------------
# RawSignal
# ---------------------------------------------------------------------------


class RawSignal(BaseModel):
    """A normalized, auditable source item before clustering.

    Raw signals are the output of the source ingestion and normalization step.
    They are stored for traceability before being clustered into opportunities.

    Attributes:
        id: Unique identifier for this signal.
        source_id: Reference to the RadarSource that produced this signal.
        external_id: Original identifier from the source (to avoid duplicates).
        title: Normalized title of the signal.
        summary: Short normalized summary or snippet.
        url: URL to the original item.
        published_at: When the original item was published.
        discovered_at: When this signal was first detected.
        content_hash: Hash of the content to detect duplicates.
        metadata: Additional signal-specific data.
        normalized_type: Source-specific type classification.
    """

    id: str = Field(default_factory=lambda: _generate_id("sig"))
    source_id: str
    external_id: str | None = None
    title: str
    summary: str | None = None
    url: str | None = None
    published_at: str | None = None
    discovered_at: str = Field(default_factory=_now_iso)
    content_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    normalized_type: str | None = None


# ---------------------------------------------------------------------------
# OpportunitySignalLink
# ---------------------------------------------------------------------------


class OpportunitySignalLink(BaseModel):
    """Joins opportunities to raw signals for many-to-many clustering.

    One opportunity can reference multiple raw signals, and one signal
    can contribute to multiple opportunities.

    Attributes:
        opportunity_id: The opportunity this link belongs to.
        raw_signal_id: The raw signal linked to the opportunity.
        link_reason: Why this signal was linked (e.g., "same_topic", "same_entity").
        created_at: When this link was created.
    """

    opportunity_id: str
    raw_signal_id: str
    link_reason: str | None = None
    created_at: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# OpportunityScore
# ---------------------------------------------------------------------------


class OpportunityScore(BaseModel):
    """Stores the scoring breakdown and explanation for an opportunity.

    Each scoring dimension is stored separately so the user can inspect
    why an opportunity received its ranking.

    Attributes:
        opportunity_id: The opportunity this score belongs to.
        strategic_relevance_score: How well this fits the user's strategy (0-100).
        novelty_score: How new this is relative to known content (0-100).
        urgency_score: How time-sensitive this opportunity is (0-100).
        evidence_score: How credible and well-supported (0-100).
        business_value_score: Expected value of acting (0-100).
        workflow_fit_score: How actionable this is right now (0-100).
        total_score: Weighted composite score (0-100).
        priority_label: User-facing priority derived from total_score.
        explanation: Human-readable explanation of the score.
        scored_at: When this score was computed.
    """

    opportunity_id: str
    strategic_relevance_score: float = 0.0
    novelty_score: float = 0.0
    urgency_score: float = 0.0
    evidence_score: float = 0.0
    business_value_score: float = 0.0
    workflow_fit_score: float = 0.0
    total_score: float = 0.0
    priority_label: PriorityLabel = PriorityLabel.MONITOR
    explanation: str | None = None
    scored_at: str = Field(default_factory=_now_iso)

    @field_validator(
        "strategic_relevance_score",
        "novelty_score",
        "urgency_score",
        "evidence_score",
        "business_value_score",
        "workflow_fit_score",
        "total_score",
        mode="before",
    )
    @classmethod
    def _clamp_score(cls, v: Any) -> float:
        """Clamp scores to 0-100 range."""
        if v is None:
            return 0.0
        try:
            val = float(v)
            return max(0.0, min(100.0, val))
        except (TypeError, ValueError):
            return 0.0

    @model_validator(mode="after")
    def _derive_priority_label(self) -> OpportunityScore:
        """Derive priority_label from total_score."""
        if self.total_score >= 80:
            self.priority_label = PriorityLabel.ACT_NOW
        elif self.total_score >= 60:
            self.priority_label = PriorityLabel.HIGH_POTENTIAL
        elif self.total_score >= 40:
            self.priority_label = PriorityLabel.MONITOR
        else:
            self.priority_label = PriorityLabel.LOW_PRIORITY
        return self


# ---------------------------------------------------------------------------
# OpportunityFeedback
# ---------------------------------------------------------------------------


class OpportunityFeedback(BaseModel):
    """Stores user response events to opportunities.

    Feedback is appended to the opportunity's feedback history so the
    system can learn from user behavior over time.

    Attributes:
        id: Unique identifier for this feedback entry.
        opportunity_id: The opportunity this feedback relates to.
        feedback_type: The type of feedback action taken.
        created_at: When the feedback was recorded.
        metadata: Additional feedback context (e.g., conversion_destination).
    """

    id: str = Field(default_factory=lambda: _generate_id("fb"))
    opportunity_id: str
    feedback_type: FeedbackType
    created_at: str = Field(default_factory=_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# WorkflowLink
# ---------------------------------------------------------------------------


class WorkflowLink(BaseModel):
    """Connects opportunities to downstream workflow objects.

    When a user converts an opportunity into a research run, brief, backlog item,
    or content pipeline, this link preserves the relationship for traceability
    and analytics.

    Attributes:
        id: Unique identifier for this workflow link.
        opportunity_id: The opportunity that triggered the workflow.
        workflow_type: Which workflow type was started.
        workflow_id: Identifier of the created workflow object.
        created_at: When the conversion happened.
    """

    id: str = Field(default_factory=lambda: _generate_id("wl"))
    opportunity_id: str
    workflow_type: WorkflowType
    workflow_id: str
    created_at: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------


class Opportunity(BaseModel):
    """A structured, decision-ready candidate shown to the user.

    Opportunities are the primary output of the Radar system. They are created
    from clustered raw signals, scored against strategy, and presented in the
    ranked inbox.

    Attributes:
        id: Unique identifier for this opportunity.
        title: Short, actionable title.
        summary: Concise description of what this opportunity is.
        opportunity_type: Category of the opportunity.
        status: Current lifecycle status.
        priority_label: User-facing priority level.
        why_it_matters: Plain-language explanation of strategic significance.
        recommended_action: Suggested next step for the user.
        first_detected_at: When this opportunity was first created.
        last_detected_at: When this opportunity was last updated with new signals.
        freshness_state: Current freshness indicator.
        total_score: Latest composite score.
        created_at: When this opportunity record was created.
        updated_at: When this opportunity record was last modified.
        metadata: Additional opportunity-specific data.
    """

    id: str = Field(default_factory=lambda: _generate_id("opp"))
    title: str
    summary: str
    opportunity_type: OpportunityType
    status: OpportunityStatus = OpportunityStatus.NEW
    priority_label: PriorityLabel = PriorityLabel.MONITOR
    why_it_matters: str | None = None
    recommended_action: str | None = None
    first_detected_at: str = Field(default_factory=_now_iso)
    last_detected_at: str = Field(default_factory=_now_iso)
    freshness_state: FreshnessState = FreshnessState.NEW
    total_score: float = 0.0
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("updated_at", mode="after")
    @classmethod
    def _touch_updated_at(cls, _: Any) -> str:
        """Update the updated_at timestamp on every serialization."""
        return _now_iso()

    def is_active(self) -> bool:
        """Return True if this opportunity is in an active state."""
        return self.status in (
            OpportunityStatus.NEW,
            OpportunityStatus.SAVED,
            OpportunityStatus.MONITORING,
        )

    def should_surface(self) -> bool:
        """Return True if this opportunity should appear in the ranked inbox."""
        if self.status in (
            OpportunityStatus.DISMISSED,
            OpportunityStatus.ARCHIVED,
            OpportunityStatus.ACTED_ON,
        ):
            return False
        if self.freshness_state == FreshnessState.EXPIRED:
            return False
        return True


# ---------------------------------------------------------------------------
# Aggregate / container models for storage
# ---------------------------------------------------------------------------


class RadarSourceList(BaseModel):
    """Container for storing a list of RadarSource records."""

    sources: list[RadarSource] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


class RawSignalList(BaseModel):
    """Container for storing a list of RawSignal records."""

    signals: list[RawSignal] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


class OpportunityList(BaseModel):
    """Container for storing a list of Opportunity records."""

    opportunities: list[Opportunity] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


class OpportunityScoreList(BaseModel):
    """Container for storing scores for all opportunities."""

    scores: list[OpportunityScore] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


class OpportunitySignalLinkList(BaseModel):
    """Container for storing all opportunity-to-signal links."""

    links: list[OpportunitySignalLink] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


class OpportunityFeedbackList(BaseModel):
    """Container for storing all feedback records."""

    feedback_entries: list[OpportunityFeedback] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


class WorkflowLinkList(BaseModel):
    """Container for storing all workflow links."""

    links: list[WorkflowLink] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)
