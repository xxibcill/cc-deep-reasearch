"""Opportunity Radar - proactive intelligence layer for cc-deep-research.

This package provides the backend infrastructure for Radar, including:
- Domain models for sources, signals, opportunities, scores, feedback, and workflow links
- YAML-based persistence for Radar entities
- Service layer for business logic operations
- FastAPI router for the Radar API surface
"""

from cc_deep_research.radar.models import (
    FeedbackType,
    FreshnessState,
    Opportunity,
    OpportunityFeedback,
    OpportunityScore,
    OpportunitySignalLink,
    OpportunityStatus,
    OpportunityType,
    PriorityLabel,
    RadarSource,
    RawSignal,
    SourceStatus,
    SourceType,
    WorkflowLink,
    WorkflowType,
)
from cc_deep_research.radar.service import RadarService
from cc_deep_research.radar.storage import RadarStore

__all__ = [
    # Models - enums
    "FeedbackType",
    "FreshnessState",
    "OpportunityStatus",
    "OpportunityType",
    "PriorityLabel",
    "SourceStatus",
    "SourceType",
    "WorkflowType",
    # Models - entities
    "RadarSource",
    "RawSignal",
    "Opportunity",
    "OpportunityScore",
    "OpportunitySignalLink",
    "OpportunityFeedback",
    "WorkflowLink",
    # Storage & service
    "RadarStore",
    "RadarService",
]
