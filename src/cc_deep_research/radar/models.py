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


class SourceHealth(StrEnum):
    """Health assessment for a Radar source."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class SourcePriority(StrEnum):
    """Priority level for a Radar source."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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
    REVIEWING = "reviewing"
    ACCEPTED = "accepted"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    CONVERTED = "converted"
    SAVED = "saved"
    ACTED_ON = "acted_on"
    MONITORING = "monitoring"
    DISMISSED = "dismissed"
    ARCHIVED = "archived"


class OpportunityOwnerPriority(StrEnum):
    """Owner priority for opportunities."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"
    DUPLICATE = "duplicate"
    STALE = "stale"
    TOO_BROAD = "too_broad"
    WRONG_AUDIENCE = "wrong_audience"


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
        owner: Owner identifier (e.g., operator name or team).
        priority: Source priority level.
        scan_cadence: How often to scan this source (e.g., "1h", "6h", "1d").
        last_scanned_at: ISO timestamp of the last scan attempt.
        last_scan_success: Whether the last scan succeeded.
        last_failure_reason: Reason for the last scan failure.
        consecutive_failures: Number of consecutive scan failures.
        health: Computed health state.
        notes: Operator notes about this source.
        created_at: When this source was added.
        updated_at: When this source was last modified.
        metadata: Additional source-specific configuration.
    """

    id: str = Field(default_factory=lambda: _generate_id("src"))
    source_type: SourceType
    label: str
    url_or_identifier: str
    status: SourceStatus = SourceStatus.ACTIVE
    owner: str | None = None
    priority: SourcePriority = SourcePriority.MEDIUM
    scan_cadence: str = "6h"
    last_scanned_at: str | None = None
    last_scan_success: bool | None = None
    last_failure_reason: str | None = None
    consecutive_failures: int = 0
    health: SourceHealth = SourceHealth.HEALTHY
    notes: str | None = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_health(self) -> RadarSource:
        """Derive health state from consecutive failures and last_scan_success."""
        if self.consecutive_failures >= 3:
            self.health = SourceHealth.UNHEALTHY
        elif self.consecutive_failures >= 1 or self.last_scan_success is False:
            self.health = SourceHealth.DEGRADED
        else:
            self.health = SourceHealth.HEALTHY
        return self


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
# StatusHistoryEntry
# ---------------------------------------------------------------------------


class StatusHistoryEntry(BaseModel):
    """Records a status transition for an opportunity.

    Each time an opportunity's status changes, a new entry is appended to
    provide a full audit trail for analytics and ranking improvements.

    Attributes:
        id: Unique identifier for this history entry.
        opportunity_id: The opportunity that changed status.
        previous_status: The status before the transition.
        new_status: The status after the transition.
        reason: Optional reason for the change (e.g., "user_action", "auto_expire").
        changed_at: When the transition occurred.
    """

    id: str = Field(default_factory=lambda: _generate_id("sh"))
    opportunity_id: str
    previous_status: OpportunityStatus
    new_status: OpportunityStatus
    reason: str | None = None
    changed_at: str = Field(default_factory=_now_iso)


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
        owner: Owner identifier (operator name or team).
        priority: Owner-assigned priority.
        reason: Reason for the current status or action.
        next_action: Suggested next step or follow-up action.
        reviewed_at: When the opportunity was last reviewed.
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
    owner: str | None = None
    priority: OpportunityOwnerPriority = OpportunityOwnerPriority.MEDIUM
    reason: str | None = None
    next_action: str | None = None
    reviewed_at: str | None = None
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

    def is_active(self) -> bool:
        """Return True if this opportunity is in an active state."""
        return self.status in (
            OpportunityStatus.NEW,
            OpportunityStatus.REVIEWING,
            OpportunityStatus.SAVED,
            OpportunityStatus.MONITORING,
        )

    def should_surface(self) -> bool:
        """Return True if this opportunity should appear in the ranked inbox."""
        if self.status in (
            OpportunityStatus.REJECTED,
            OpportunityStatus.DISMISSED,
            OpportunityStatus.ARCHIVED,
            OpportunityStatus.ACTED_ON,
            OpportunityStatus.CONVERTED,
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


class StatusHistoryList(BaseModel):
    """Container for storing all status history entries."""

    entries: list[StatusHistoryEntry] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Scan Job models (for scheduled scans)
# ---------------------------------------------------------------------------


class ScanJobStatus(StrEnum):
    """Status of a scan job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ScanJob(BaseModel):
    """Records a scan job execution.

    Scan jobs track the execution of scheduled or manual scans
    for audit and diagnostics purposes.

    Attributes:
        id: Unique identifier for this scan job.
        source_id: The source that was scanned (or None for multi-source).
        triggered_by: What triggered this scan (schedule, manual, dry_run).
        status: Current status of the job.
        signals_found: Number of signals found in this scan.
        errors: Error messages encountered during scan.
        started_at: When the scan started.
        completed_at: When the scan completed (or None if not done).
        scan_type: Type of scan (full, incremental, dry_run).
    """

    id: str = Field(default_factory=lambda: _generate_id("sj"))
    source_id: str | None = None
    triggered_by: str = "schedule"
    status: ScanJobStatus = ScanJobStatus.PENDING
    signals_found: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: str = Field(default_factory=_now_iso)
    completed_at: str | None = None
    scan_type: str = "full"


class ScanJobList(BaseModel):
    """Container for storing scan job records."""

    jobs: list[ScanJob] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Alert and digest models
# ---------------------------------------------------------------------------


class AlertSeverity(StrEnum):
    """Severity level for Radar alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertTrigger(StrEnum):
    """What conditions trigger a Radar alert."""

    HIGH_PRIORITY_OPPORTUNITY = "high_priority_opportunity"
    SOURCE_FAILURE = "source_failure"
    STALE_SCAN = "stale_scan"
    VOLUME_SPIKE = "volume_spike"
    CONSECUTIVE_FAILURES = "consecutive_failures"


class RadarAlert(BaseModel):
    """An alert generated by the Radar system.

    Alerts notify operators of important events that require attention.

    Attributes:
        id: Unique identifier for this alert.
        trigger: What triggered this alert.
        severity: How severe the alert is.
        title: Short alert title.
        message: Detailed alert message.
        source_id: Related source ID (if applicable).
        opportunity_id: Related opportunity ID (if applicable).
        acknowledged: Whether the alert has been acknowledged.
        acknowledged_by: Who acknowledged the alert.
        acknowledged_at: When the alert was acknowledged.
        created_at: When the alert was created.
        metadata: Additional alert data.
    """

    id: str = Field(default_factory=lambda: _generate_id("alrt"))
    trigger: AlertTrigger
    severity: AlertSeverity = AlertSeverity.INFO
    title: str
    message: str
    source_id: str | None = None
    opportunity_id: str | None = None
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None
    created_at: str = Field(default_factory=_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RadarAlertList(BaseModel):
    """Container for storing RadarAlert records."""

    alerts: list[RadarAlert] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


class RadarDigest(BaseModel):
    """A digest summarizing Radar activity over a period.

    Digests provide a structured summary of opportunities and issues
    for periodic review.

    Attributes:
        id: Unique identifier for this digest.
        period_start: Start of the digest period.
        period_end: End of the digest period.
        new_opportunities_count: Number of new opportunities in the period.
        top_opportunities: Top opportunities from the period.
        source_health_issues: Sources with health issues.
        alert_count: Total alerts in the period.
        created_at: When the digest was created.
    """

    id: str = Field(default_factory=lambda: _generate_id("dgst"))
    period_start: str
    period_end: str
    new_opportunities_count: int = 0
    top_opportunities: list[dict[str, Any]] = Field(default_factory=list)
    source_health_issues: list[dict[str, Any]] = Field(default_factory=list)
    alert_count: int = 0
    created_at: str = Field(default_factory=_now_iso)


class RadarDigestList(BaseModel):
    """Container for storing RadarDigest records."""

    digests: list[RadarDigest] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


class AlertMute(BaseModel):
    """Mutes an alert trigger for a specific source or globally.

    Attributes:
        id: Unique identifier.
        trigger: The alert trigger to mute.
        source_id: Source to mute (None for global).
        muted_by: Who muted this trigger.
        muted_at: When the mute was created.
        expires_at: When the mute expires (None for permanent).
    """

    id: str = Field(default_factory=lambda: _generate_id("mute"))
    trigger: AlertTrigger
    source_id: str | None = None
    muted_by: str | None = None
    muted_at: str = Field(default_factory=_now_iso)
    expires_at: str | None = None


class AlertMuteList(BaseModel):
    """Container for storing AlertMute records."""

    mutes: list[AlertMute] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Scoring feedback models
# ---------------------------------------------------------------------------


class ScoringFeedback(BaseModel):
    """Feedback on opportunity scoring for tuning purposes.

    Stores the outcome of scoring to enable tuning of future rankings.

    Attributes:
        id: Unique identifier.
        opportunity_id: The opportunity that was scored.
        signal_id: The signal that contributed to the score (optional).
        feedback_type: Type of relevance feedback.
        scoring_features: The feature scores at time of ranking.
        rank_position: Position in ranking when shown.
        outcome: Whether the operator acted on this opportunity.
        created_at: When feedback was recorded.
    """

    id: str = Field(default_factory=lambda: _generate_id("sf"))
    opportunity_id: str
    signal_id: str | None = None
    feedback_type: FeedbackType
    scoring_features: dict[str, float] = Field(default_factory=dict)
    rank_position: int | None = None
    outcome: str | None = None
    created_at: str = Field(default_factory=_now_iso)


class ScoringFeedbackList(BaseModel):
    """Container for storing ScoringFeedback records."""

    feedback_entries: list[ScoringFeedback] = Field(default_factory=list)
    last_updated: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Analytics models
# ---------------------------------------------------------------------------


class RadarAnalytics(BaseModel):
    """Aggregated analytics for the Radar feature.

    Provides summary statistics for operators to understand radar performance
    and tune the system over time.

    Attributes:
        total_opportunities: Total number of opportunities ever created.
        opportunities_by_status: Count of opportunities per status.
        opportunities_by_type: Count of opportunities per type.
        feedback_counts: Count of each feedback type.
        conversion_rates: Percentage of opportunities that received each workflow type.
        avg_time_to_action: Average hours from creation to first action.
        top_opportunity_types: Most common opportunity types by count.
    """

    total_opportunities: int = 0
    opportunities_by_status: dict[str, int] = Field(default_factory=dict)
    opportunities_by_type: dict[str, int] = Field(default_factory=dict)
    feedback_counts: dict[str, int] = Field(default_factory=dict)
    conversion_rates: dict[str, float] = Field(default_factory=dict)
    avg_time_to_action_hours: float | None = None
    top_opportunity_types: list[tuple[str, int]] = Field(default_factory=list)
