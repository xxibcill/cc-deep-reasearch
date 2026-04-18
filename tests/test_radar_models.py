"""Tests for Radar domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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


class TestRadarSource:
    """Tests for RadarSource model."""

    def test_valid_construction(self) -> None:
        """RadarSource can be constructed with required fields."""
        src = RadarSource(
            source_type=SourceType.NEWS,
            label="TechCrunch",
            url_or_identifier="https://techcrunch.com/feed",
        )
        assert src.source_type == SourceType.NEWS
        assert src.label == "TechCrunch"
        assert src.url_or_identifier == "https://techcrunch.com/feed"
        assert src.status == SourceStatus.ACTIVE
        assert src.scan_cadence == "6h"
        assert src.id.startswith("src-")
        assert src.created_at is not None

    def test_all_source_types(self) -> None:
        """All SourceType values are valid."""
        for st in SourceType:
            src = RadarSource(source_type=st, label="Test", url_or_identifier="http://test.com")
            assert src.source_type == st

    def test_source_status_default(self) -> None:
        """Default status is ACTIVE."""
        src = RadarSource(source_type=SourceType.BLOG, label="Test", url_or_identifier="http://test.com")
        assert src.status == SourceStatus.ACTIVE

    def test_metadata_optional(self) -> None:
        """Metadata field defaults to empty dict."""
        src = RadarSource(source_type=SourceType.COMPETITOR, label="Test", url_or_identifier="http://test.com")
        assert src.metadata == {}


class TestRawSignal:
    """Tests for RawSignal model."""

    def test_valid_construction(self) -> None:
        """RawSignal can be constructed with required fields."""
        sig = RawSignal(
            source_id="src-abc123",
            title="New AI Model Released",
            summary="OpenAI released GPT-5 today",
            url="https://example.com/article",
        )
        assert sig.source_id == "src-abc123"
        assert sig.title == "New AI Model Released"
        assert sig.summary == "OpenAI released GPT-5 today"
        assert sig.discovered_at is not None
        assert sig.id.startswith("sig-")

    def test_optional_fields_default(self) -> None:
        """Optional fields have sensible defaults."""
        sig = RawSignal(source_id="src-abc", title="Test Signal")
        assert sig.external_id is None
        assert sig.summary is None
        assert sig.url is None
        assert sig.published_at is None
        assert sig.content_hash is None
        assert sig.normalized_type is None


class TestOpportunity:
    """Tests for Opportunity model."""

    def test_valid_construction(self) -> None:
        """Opportunity can be constructed with required fields."""
        opp = Opportunity(
            title="Competitor launched new product",
            summary="Acme Corp released a direct competitor to our flagship offering",
            opportunity_type=OpportunityType.COMPETITOR_MOVE,
        )
        assert opp.title == "Competitor launched new product"
        assert opp.status == OpportunityStatus.NEW
        assert opp.freshness_state == FreshnessState.NEW
        assert opp.id.startswith("opp-")
        assert opp.first_detected_at is not None
        assert opp.last_detected_at is not None

    def test_all_opportunity_types(self) -> None:
        """All OpportunityType values are valid."""
        for ot in OpportunityType:
            opp = Opportunity(title="Test", summary="Test", opportunity_type=ot)
            assert opp.opportunity_type == ot

    def test_all_status_values(self) -> None:
        """All OpportunityStatus values are valid."""
        for status in OpportunityStatus:
            opp = Opportunity(
                title="Test",
                summary="Test",
                opportunity_type=OpportunityType.RISING_TOPIC,
                status=status,
            )
            assert opp.status == status

    def test_all_freshness_states(self) -> None:
        """All FreshnessState values are valid."""
        for fs in FreshnessState:
            opp = Opportunity(
                title="Test",
                summary="Test",
                opportunity_type=OpportunityType.NARRATIVE_SHIFT,
                freshness_state=fs,
            )
            assert opp.freshness_state == fs

    def test_priority_label_default(self) -> None:
        """Default priority label is MONITOR."""
        opp = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.PROOF_POINT,
        )
        assert opp.priority_label == PriorityLabel.MONITOR

    def test_is_active(self) -> None:
        """is_active returns True for active statuses."""
        active_statuses = [OpportunityStatus.NEW, OpportunityStatus.SAVED, OpportunityStatus.MONITORING]
        for status in active_statuses:
            opp = Opportunity(
                title="Test",
                summary="Test",
                opportunity_type=OpportunityType.AUDIENCE_QUESTION,
                status=status,
            )
            assert opp.is_active() is True

    def test_is_not_active(self) -> None:
        """is_active returns False for inactive statuses."""
        inactive_statuses = [
            OpportunityStatus.DISMISSED,
            OpportunityStatus.ARCHIVED,
            OpportunityStatus.ACTED_ON,
        ]
        for status in inactive_statuses:
            opp = Opportunity(
                title="Test",
                summary="Test",
                opportunity_type=OpportunityType.RISING_TOPIC,
                status=status,
            )
            assert opp.is_active() is False

    def test_should_surface_active(self) -> None:
        """should_surface returns True for active, non-expired opportunities."""
        opp = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.COMPETITOR_MOVE,
            status=OpportunityStatus.NEW,
            freshness_state=FreshnessState.FRESH,
        )
        assert opp.should_surface() is True

    def test_should_not_surface_dismissed(self) -> None:
        """should_surface returns False for dismissed opportunities."""
        opp = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.LAUNCH_UPDATE_CHANGE,
            status=OpportunityStatus.DISMISSED,
        )
        assert opp.should_surface() is False

    def test_should_not_surface_expired(self) -> None:
        """should_surface returns False for expired freshness state."""
        opp = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.PROOF_POINT,
            freshness_state=FreshnessState.EXPIRED,
        )
        assert opp.should_surface() is False


class TestOpportunityScore:
    """Tests for OpportunityScore model."""

    def test_valid_construction(self) -> None:
        """OpportunityScore can be constructed with required fields."""
        score = OpportunityScore(opportunity_id="opp-abc123")
        assert score.opportunity_id == "opp-abc123"
        assert score.total_score == 0.0
        assert score.scored_at is not None

    def test_score_clamping(self) -> None:
        """Scores are clamped to 0-100 range."""
        score = OpportunityScore(
            opportunity_id="opp-xyz",
            strategic_relevance_score=150.0,
            novelty_score=-10.0,
        )
        assert score.strategic_relevance_score == 100.0
        assert score.novelty_score == 0.0

    def test_priority_label_derivation_high(self) -> None:
        """Total score >= 80 derives ACT_NOW priority."""
        score = OpportunityScore(
            opportunity_id="opp-high",
            total_score=85.0,
            strategic_relevance_score=90.0,
            novelty_score=80.0,
            urgency_score=85.0,
            evidence_score=80.0,
            business_value_score=85.0,
            workflow_fit_score=80.0,
        )
        assert score.priority_label == PriorityLabel.ACT_NOW

    def test_priority_label_derivation_medium(self) -> None:
        """Total score >= 60 derives HIGH_POTENTIAL priority."""
        score = OpportunityScore(
            opportunity_id="opp-med",
            total_score=65.0,
            strategic_relevance_score=70.0,
            novelty_score=60.0,
            urgency_score=65.0,
            evidence_score=60.0,
            business_value_score=65.0,
            workflow_fit_score=60.0,
        )
        assert score.priority_label == PriorityLabel.HIGH_POTENTIAL

    def test_priority_label_derivation_low(self) -> None:
        """Total score >= 40 derives MONITOR priority."""
        score = OpportunityScore(
            opportunity_id="opp-low",
            total_score=45.0,
            strategic_relevance_score=50.0,
            novelty_score=40.0,
            urgency_score=45.0,
            evidence_score=40.0,
            business_value_score=45.0,
            workflow_fit_score=40.0,
        )
        assert score.priority_label == PriorityLabel.MONITOR

    def test_priority_label_derivation_very_low(self) -> None:
        """Total score < 40 derives LOW_PRIORITY priority."""
        score = OpportunityScore(
            opportunity_id="opp-vlow",
            total_score=30.0,
            strategic_relevance_score=30.0,
            novelty_score=30.0,
            urgency_score=30.0,
            evidence_score=30.0,
            business_value_score=30.0,
            workflow_fit_score=30.0,
        )
        assert score.priority_label == PriorityLabel.LOW_PRIORITY


class TestOpportunityFeedback:
    """Tests for OpportunityFeedback model."""

    def test_valid_construction(self) -> None:
        """OpportunityFeedback can be constructed with required fields."""
        fb = OpportunityFeedback(
            opportunity_id="opp-abc",
            feedback_type=FeedbackType.SAVED,
        )
        assert fb.opportunity_id == "opp-abc"
        assert fb.feedback_type == FeedbackType.SAVED
        assert fb.id.startswith("fb-")
        assert fb.created_at is not None

    def test_all_feedback_types(self) -> None:
        """All FeedbackType values are valid."""
        for ft in FeedbackType:
            fb = OpportunityFeedback(opportunity_id="opp-test", feedback_type=ft)
            assert fb.feedback_type == ft

    def test_metadata_optional(self) -> None:
        """Metadata defaults to empty dict."""
        fb = OpportunityFeedback(
            opportunity_id="opp-test",
            feedback_type=FeedbackType.DISMISSED,
        )
        assert fb.metadata == {}


class TestWorkflowLink:
    """Tests for WorkflowLink model."""

    def test_valid_construction(self) -> None:
        """WorkflowLink can be constructed with required fields."""
        link = WorkflowLink(
            opportunity_id="opp-abc",
            workflow_type=WorkflowType.RESEARCH_RUN,
            workflow_id="session-xyz-123",
        )
        assert link.opportunity_id == "opp-abc"
        assert link.workflow_type == WorkflowType.RESEARCH_RUN
        assert link.workflow_id == "session-xyz-123"
        assert link.id.startswith("wl-")
        assert link.created_at is not None

    def test_all_workflow_types(self) -> None:
        """All WorkflowType values are valid."""
        for wt in WorkflowType:
            link = WorkflowLink(
                opportunity_id="opp-test",
                workflow_type=wt,
                workflow_id="test-id",
            )
            assert link.workflow_type == wt


class TestOpportunitySignalLink:
    """Tests for OpportunitySignalLink model."""

    def test_valid_construction(self) -> None:
        """OpportunitySignalLink can be constructed with required fields."""
        link = OpportunitySignalLink(
            opportunity_id="opp-abc",
            raw_signal_id="sig-xyz",
            link_reason="same_topic",
        )
        assert link.opportunity_id == "opp-abc"
        assert link.raw_signal_id == "sig-xyz"
        assert link.link_reason == "same_topic"
        assert link.created_at is not None

    def test_link_reason_optional(self) -> None:
        """link_reason is optional."""
        link = OpportunitySignalLink(
            opportunity_id="opp-abc",
            raw_signal_id="sig-xyz",
        )
        assert link.link_reason is None
