"""API request and response models for Radar endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateSourceRequest(BaseModel):
    """Request body for creating a RadarSource."""

    source_type: Literal[
        "news", "blog", "changelog", "forum", "social", "competitor", "custom"
    ] = Field(min_length=1)
    label: str = Field(min_length=1)
    url_or_identifier: str = Field(min_length=1)
    scan_cadence: str = Field(default="6h")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ListOpportunitiesRequest(BaseModel):
    """Query params for listing opportunities."""

    status: str | None = None
    opportunity_type: str | None = None
    freshness: str | None = None
    limit: int | None = None


class UpdateOpportunityStatusRequest(BaseModel):
    """Request body for updating an opportunity status."""

    status: Literal["new", "saved", "acted_on", "monitoring", "dismissed", "archived"]


class RecordFeedbackRequest(BaseModel):
    """Request body for recording feedback on an opportunity."""

    feedback_type: Literal[
        "acted_on", "saved", "dismissed", "ignored", "converted_to_research", "converted_to_content"
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpportunityResponse(BaseModel):
    """Response shape for a single opportunity."""

    id: str
    title: str
    summary: str
    opportunity_type: str
    status: str
    priority_label: str
    why_it_matters: str | None
    recommended_action: str | None
    total_score: float
    freshness_state: str
    created_at: str
    updated_at: str


class OpportunityDetailResponse(BaseModel):
    """Response shape for opportunity detail with signals, score, feedback."""

    opportunity: dict[str, Any]
    score: dict[str, Any] | None
    signals: list[dict[str, Any]]
    feedback: list[dict[str, Any]]
    workflow_links: list[dict[str, Any]]


class SourceResponse(BaseModel):
    """Response shape for a single RadarSource."""

    id: str
    source_type: str
    label: str
    url_or_identifier: str
    status: str
    scan_cadence: str
    last_scanned_at: str | None
    created_at: str
    updated_at: str


class OpportunityListResponse(BaseModel):
    """Response shape for opportunity list."""

    items: list[dict[str, Any]]
    count: int


class SourceListResponse(BaseModel):
    """Response shape for source list."""

    items: list[dict[str, Any]]
    count: int


class LaunchResearchResponse(BaseModel):
    """Response for launching a research run from an opportunity."""

    research_run_id: str
    opportunity_id: str
    status: str = "queued"
    session_id: str | None = None


class LaunchBriefResponse(BaseModel):
    """Response for launching a brief from an opportunity."""

    brief_id: str
    opportunity_id: str


class LaunchBacklogResponse(BaseModel):
    """Response for adding opportunity to backlog."""

    backlog_item_id: str
    opportunity_id: str


class LaunchContentPipelineResponse(BaseModel):
    """Response for launching a content pipeline from an opportunity."""

    pipeline_id: str
    opportunity_id: str
    status: str = "queued"


class StatusHistoryResponse(BaseModel):
    """Response for status history of an opportunity."""

    entries: list[dict[str, Any]]
    count: int


class RadarAnalyticsResponse(BaseModel):
    """Response for radar analytics summary."""

    total_opportunities: int
    opportunities_by_status: dict[str, int]
    opportunities_by_type: dict[str, int]
    feedback_counts: dict[str, int]
    conversion_rates: dict[str, float]
    avg_time_to_action_hours: float | None
    top_opportunity_types: list[tuple[str, int]]


class ConversionFunnelResponse(BaseModel):
    """Response for conversion funnel data."""

    funnel: list[dict[str, Any]]
    total: int


class FeedbackTrendsResponse(BaseModel):
    """Response for feedback trends data."""

    daily_counts: dict[str, dict[str, int]]
    days_back: int


class ScoreDistributionResponse(BaseModel):
    """Response for score distribution."""

    distribution: dict[str, int]
    total: int
    avg_score: float


# -- Source governance API models ---

class UpdateSourceRequest(BaseModel):
    """Request body for updating a RadarSource."""

    owner: str | None = None
    priority: str | None = None
    scan_cadence: str | None = None
    status: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class SourceHealthResponse(BaseModel):
    """Response for source health details."""

    source_id: str
    health: str
    consecutive_failures: int
    last_failure_reason: str | None
    last_scan_success: bool | None
    last_scanned_at: str | None
    recent_jobs: list[dict[str, Any]]


class ListSourcesRequest(BaseModel):
    """Query params for listing sources with governance filters."""

    status: str | None = None
    health: str | None = None
    priority: str | None = None
    owner: str | None = None


# -- Scan job API models ---

class ScanJobResponse(BaseModel):
    """Response for a scan job."""

    id: str
    source_id: str | None
    triggered_by: str
    status: str
    signals_found: int
    errors: list[str]
    started_at: str
    completed_at: str | None
    scan_type: str


class ScanHistoryResponse(BaseModel):
    """Response for scan history."""

    jobs: list[dict[str, Any]]
    count: int


class DryRunResponse(BaseModel):
    """Response for dry-run scan preview."""

    sources: list[dict[str, Any]]
    job_count: int
    dry_run: bool


class TriggerScanRequest(BaseModel):
    """Request body for triggering an immediate scan."""

    source_id: str


# -- Alert API models ---

class RadarAlertResponse(BaseModel):
    """Response for a Radar alert."""

    id: str
    trigger: str
    severity: str
    title: str
    message: str
    source_id: str | None
    opportunity_id: str | None
    acknowledged: bool
    acknowledged_by: str | None
    acknowledged_at: str | None
    created_at: str
    metadata: dict[str, Any]


class AlertListResponse(BaseModel):
    """Response for listing alerts."""

    alerts: list[dict[str, Any]]
    count: int
    unacknowledged_count: int


class AcknowledgeAlertRequest(BaseModel):
    """Request body for acknowledging an alert."""

    acknowledged_by: str


class MuteAlertRequest(BaseModel):
    """Request body for muting an alert trigger."""

    trigger: str
    source_id: str | None = None
    expires_at: str | None = None


class AlertMuteResponse(BaseModel):
    """Response for an alert mute."""

    id: str
    trigger: str
    source_id: str | None
    muted_by: str | None
    muted_at: str
    expires_at: str | None


class MuteListResponse(BaseModel):
    """Response for listing alert mutes."""

    mutes: list[dict[str, Any]]
    count: int


# -- Digest API models ---

class RadarDigestResponse(BaseModel):
    """Response for a Radar digest."""

    id: str
    period_start: str
    period_end: str
    new_opportunities_count: int
    top_opportunities: list[dict[str, Any]]
    source_health_issues: list[dict[str, Any]]
    alert_count: int
    created_at: str


class DigestListResponse(BaseModel):
    """Response for listing digests."""

    digests: list[dict[str, Any]]
    count: int


class GenerateDigestRequest(BaseModel):
    """Request body for generating a digest."""

    period_start: str
    period_end: str


# -- Scoring feedback API models ---

class RecordScoringFeedbackRequest(BaseModel):
    """Request body for recording scoring feedback."""

    feedback_type: str
    signal_id: str | None = None
    scoring_features: dict[str, float] | None = None
    rank_position: int | None = None
    outcome: str | None = None


class ScoringFeedbackResponse(BaseModel):
    """Response for a scoring feedback entry."""

    id: str
    opportunity_id: str
    signal_id: str | None
    feedback_type: str
    scoring_features: dict[str, float]
    rank_position: int | None
    outcome: str | None
    created_at: str


class ScoringFeedbackListResponse(BaseModel):
    """Response for listing scoring feedback."""

    feedback_entries: list[dict[str, Any]]
    count: int


class ScoringOutcomesResponse(BaseModel):
    """Response for scoring outcome analysis."""

    outcomes: dict[str, int]
    total_feedback: int


# -- Bulk operations API models ---

class BulkUpdateStatusRequest(BaseModel):
    """Request body for bulk status update."""

    opportunity_ids: list[str]
    status: str
    reason: str | None = None


class BulkUpdateStatusResponse(BaseModel):
    """Response for bulk status update."""

    updated: list[dict[str, Any]]
    count: int


# -- Update opportunity with lifecycle fields ---

class UpdateOpportunityRequest(BaseModel):
    """Request body for updating an opportunity with lifecycle fields."""

    status: str | None = None
    owner: str | None = None
    priority: str | None = None
    reason: str | None = None
    next_action: str | None = None
    reviewed_at: str | None = None
