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
