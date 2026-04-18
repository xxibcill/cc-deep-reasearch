"""Tests for RadarService using temporary directories."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_deep_research.radar.models import (
    FeedbackType,
    FreshnessState,
    Opportunity,
    OpportunityFeedback,
    OpportunityScore,
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


@pytest.fixture
def temp_radar_dir(tmp_path: Path) -> Path:
    """Return a temporary radar directory."""
    return tmp_path / "radar"


@pytest.fixture
def store(temp_radar_dir: Path) -> RadarStore:
    """Return a RadarStore backed by a temporary directory."""
    return RadarStore(radar_dir=temp_radar_dir)


@pytest.fixture
def service(store: RadarStore) -> RadarService:
    """Return a RadarService backed by the temporary store."""
    return RadarService(store=store)


class TestRadarServiceSources:
    """Tests for RadarService source operations."""

    def test_create_source(self, service: RadarService) -> None:
        """create_source persists a new source and returns it."""
        src = service.create_source(
            source_type="news",
            label="TechCrunch",
            url_or_identifier="https://techcrunch.com/feed",
        )
        assert src.label == "TechCrunch"
        assert src.source_type == SourceType.NEWS
        assert src.id.startswith("src-")

    def test_create_source_with_cadence(self, service: RadarService) -> None:
        """create_source respects scan_cadence parameter."""
        src = service.create_source(
            source_type="blog",
            label="My Blog",
            url_or_identifier="http://myblog.com/rss",
            scan_cadence="1h",
        )
        assert src.scan_cadence == "1h"

    def test_list_sources(self, service: RadarService) -> None:
        """list_sources returns all sources."""
        service.create_source("news", "Source 1", "http://s1.com")
        service.create_source("blog", "Source 2", "http://s2.com")

        sources = service.list_sources()
        assert len(sources) == 2

    def test_list_sources_filter_by_status(self, service: RadarService) -> None:
        """list_sources can filter by status."""
        service.create_source("news", "Active Source", "http://active.com")
        inactive = service.create_source("news", "Inactive Source", "http://inactive.com")
        service.update_source_status(inactive.id, "inactive")

        active_sources = service.list_sources(status="active")
        assert len(active_sources) == 1
        assert active_sources[0].label == "Active Source"

    def test_update_source_status(self, service: RadarService) -> None:
        """update_source_status changes the source status."""
        src = service.create_source("forum", "Forum", "http://forum.com")
        updated = service.update_source_status(src.id, "inactive")
        assert updated is not None
        assert updated.status == SourceStatus.INACTIVE


class TestRadarServiceSignals:
    """Tests for RadarService signal operations."""

    def test_add_signal(self, service: RadarService) -> None:
        """add_signal persists a signal and returns it."""
        src = service.create_source("news", "News", "http://news.com")
        sig = service.add_signal(
            source_id=src.id,
            title="Breaking: New AI Model",
            summary="A new model was released",
            url="http://news.com/article",
        )
        assert sig.title == "Breaking: New AI Model"
        assert sig.source_id == src.id


class TestRadarServiceOpportunities:
    """Tests for RadarService opportunity operations."""

    def test_create_opportunity(self, service: RadarService) -> None:
        """create_opportunity persists and returns the opportunity."""
        opp = service.create_opportunity(
            title="Competitor launched new product",
            summary="A competitor released something new",
            opportunity_type="competitor_move",
            why_it_matters="Direct competition",
        )
        assert opp.title == "Competitor launched new product"
        assert opp.opportunity_type == OpportunityType.COMPETITOR_MOVE
        assert opp.why_it_matters == "Direct competition"
        assert opp.status == OpportunityStatus.NEW

    def test_list_opportunities(self, service: RadarService) -> None:
        """list_opportunities returns all opportunities."""
        service.create_opportunity("Opp 1", "Summary 1", "rising_topic")
        service.create_opportunity("Opp 2", "Summary 2", "audience_question")

        opportunities = service.list_opportunities()
        assert len(opportunities) == 2

    def test_list_opportunities_filter_by_status(self, service: RadarService) -> None:
        """list_opportunities filters by status."""
        opp1 = service.create_opportunity("New Opp", "Summary", "rising_topic")
        opp2 = service.create_opportunity("Saved Opp", "Summary", "rising_topic")
        service.update_opportunity_status(opp2.id, "saved")

        results = service.list_opportunities(status="new")
        assert len(results) == 1
        assert results[0].id == opp1.id

    def test_list_opportunities_filter_by_type(self, service: RadarService) -> None:
        """list_opportunities filters by opportunity_type."""
        service.create_opportunity("Type A", "Summary", "competitor_move")
        service.create_opportunity("Type B", "Summary", "rising_topic")

        results = service.list_opportunities(opportunity_type="rising_topic")
        assert len(results) == 1
        assert results[0].opportunity_type == OpportunityType.RISING_TOPIC

    def test_get_opportunity_detail(self, service: RadarService) -> None:
        """get_opportunity_detail returns full detail dict."""
        opp = service.create_opportunity("Test", "Summary", "rising_topic")

        detail = service.get_opportunity_detail(opp.id)
        assert detail is not None
        assert detail["opportunity"].id == opp.id
        assert detail["score"] is None
        assert detail["signals"] == []
        assert detail["feedback"] == []

    def test_get_opportunity_detail_not_found(self, service: RadarService) -> None:
        """get_opportunity_detail returns None for non-existent id."""
        detail = service.get_opportunity_detail("opp-does-not-exist")
        assert detail is None

    def test_update_opportunity_status(self, service: RadarService) -> None:
        """update_opportunity_status changes the status."""
        opp = service.create_opportunity("Status Test", "Summary", "rising_topic")
        updated = service.update_opportunity_status(opp.id, "saved")
        assert updated is not None
        assert updated.status == OpportunityStatus.SAVED


class TestRadarServiceScores:
    """Tests for RadarService score operations."""

    def test_save_score(self, service: RadarService) -> None:
        """save_score computes total and persists the score."""
        opp = service.create_opportunity("Scored", "Summary", "rising_topic")

        score = service.save_score(
            opportunity_id=opp.id,
            strategic_relevance_score=80.0,
            novelty_score=70.0,
            urgency_score=75.0,
            evidence_score=65.0,
            business_value_score=85.0,
            workflow_fit_score=60.0,
            explanation="Strong strategic fit",
        )

        assert score.opportunity_id == opp.id
        # 80*0.30 + 70*0.10 + 75*0.15 + 65*0.15 + 85*0.20 + 60*0.10
        # = 24 + 7 + 11.25 + 9.75 + 17 + 6 = 75.0
        assert score.total_score == 75.0
        assert score.priority_label == PriorityLabel.HIGH_POTENTIAL
        assert score.explanation == "Strong strategic fit"

        # Also verify the opportunity's total_score was updated
        updated_opp = service._store.get_opportunity(opp.id)
        assert updated_opp is not None
        assert updated_opp.total_score == 75.0

    def test_save_score_act_now(self, service: RadarService) -> None:
        """Score >= 80 gets ACT_NOW priority."""
        opp = service.create_opportunity("Top Score", "Summary", "rising_topic")

        score = service.save_score(
            opportunity_id=opp.id,
            strategic_relevance_score=90.0,
            novelty_score=85.0,
            urgency_score=90.0,
            evidence_score=85.0,
            business_value_score=90.0,
            workflow_fit_score=85.0,
        )

        assert score.total_score >= 80.0
        assert score.priority_label == PriorityLabel.ACT_NOW


class TestRadarServiceFeedback:
    """Tests for RadarService feedback operations."""

    def test_record_feedback(self, service: RadarService) -> None:
        """record_feedback creates a feedback entry."""
        opp = service.create_opportunity("Feedback Test", "Summary", "rising_topic")

        fb = service.record_feedback(
            opportunity_id=opp.id,
            feedback_type="saved",
        )

        assert fb.opportunity_id == opp.id
        assert fb.feedback_type == FeedbackType.SAVED

    def test_record_feedback_with_metadata(self, service: RadarService) -> None:
        """record_feedback accepts metadata."""
        opp = service.create_opportunity("Metadata", "Summary", "rising_topic")

        fb = service.record_feedback(
            opportunity_id=opp.id,
            feedback_type="acted_on",
            metadata={"converted_to": "research_run", "session_id": "abc"},
        )

        assert fb.metadata["converted_to"] == "research_run"


class TestRadarServiceWorkflowLinks:
    """Tests for RadarService workflow link operations."""

    def test_link_workflow(self, service: RadarService) -> None:
        """link_workflow creates a workflow link."""
        opp = service.create_opportunity("Convert", "Summary", "rising_topic")

        link = service.link_workflow(
            opportunity_id=opp.id,
            workflow_type="research_run",
            workflow_id="session-new-123",
        )

        assert link.opportunity_id == opp.id
        assert link.workflow_type == WorkflowType.RESEARCH_RUN
        assert link.workflow_id == "session-new-123"
