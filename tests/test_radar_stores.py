"""Tests for RadarStore persistence using temporary directories."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_deep_research.radar.models import (
    Opportunity,
    OpportunityFeedback,
    OpportunityScore,
    OpportunityStatus,
    OpportunityType,
    RadarSource,
    RawSignal,
    SourceStatus,
    SourceType,
    WorkflowLink,
    WorkflowType,
)
from cc_deep_research.radar.storage import RadarStore


@pytest.fixture
def temp_radar_dir(tmp_path: Path) -> Path:
    """Return a temporary radar directory."""
    return tmp_path / "radar"


@pytest.fixture
def store(temp_radar_dir: Path) -> RadarStore:
    """Return a RadarStore backed by a temporary directory."""
    return RadarStore(radar_dir=temp_radar_dir)


class TestRadarStoreSources:
    """Tests for RadarStore source operations."""

    def test_load_sources_empty(self, store: RadarStore) -> None:
        """Loading from a fresh store returns an empty list."""
        result = store.load_sources()
        assert result.sources == []

    def test_add_source(self, store: RadarStore) -> None:
        """Adding a source persists it."""
        src = RadarSource(
            source_type=SourceType.NEWS,
            label="Hacker News",
            url_or_identifier="https://news.ycombinator.com",
        )
        store.add_source(src)
        result = store.load_sources()
        assert len(result.sources) == 1
        assert result.sources[0].label == "Hacker News"

    def test_get_source(self, store: RadarStore) -> None:
        """Getting a source by id returns the source."""
        src = RadarSource(
            source_type=SourceType.BLOG,
            label="Test Blog",
            url_or_identifier="http://test.com",
        )
        store.add_source(src)
        result = store.get_source(src.id)
        assert result is not None
        assert result.label == "Test Blog"

    def test_get_source_not_found(self, store: RadarStore) -> None:
        """Getting a non-existent source returns None."""
        result = store.get_source("src-nonexistent")
        assert result is None

    def test_update_source(self, store: RadarStore) -> None:
        """Updating a source persists the change."""
        src = RadarSource(
            source_type=SourceType.FORUM,
            label="Old Label",
            url_or_identifier="http://forum.com",
        )
        store.add_source(src)
        updated = store.update_source(src.id, {"label": "New Label", "status": SourceStatus.INACTIVE})
        assert updated is not None
        assert updated.label == "New Label"
        assert updated.status == SourceStatus.INACTIVE

    def test_delete_source(self, store: RadarStore) -> None:
        """Deleting a source removes it from storage."""
        src = RadarSource(
            source_type=SourceType.SOCIAL,
            label="To Delete",
            url_or_identifier="http://delete.com",
        )
        store.add_source(src)
        deleted = store.delete_source(src.id)
        assert deleted is True
        assert store.get_source(src.id) is None

    def test_delete_source_not_found(self, store: RadarStore) -> None:
        """Deleting a non-existent source returns False."""
        result = store.delete_source("src-does-not-exist")
        assert result is False


class TestRadarStoreSignals:
    """Tests for RadarStore signal operations."""

    def test_add_signal(self, store: RadarStore) -> None:
        """Adding a signal persists it."""
        sig = RawSignal(source_id="src-abc", title="New Signal")
        store.add_signal(sig)
        result = store.load_signals()
        assert len(result.signals) == 1
        assert result.signals[0].title == "New Signal"

    def test_add_signals_batch(self, store: RadarStore) -> None:
        """Adding multiple signals persists all."""
        signals = [
            RawSignal(source_id="src-1", title=f"Signal {i}")
            for i in range(3)
        ]
        store.add_signals(signals)
        result = store.load_signals()
        assert len(result.signals) == 3

    def test_get_signal(self, store: RadarStore) -> None:
        """Getting a signal by id returns it."""
        sig = RawSignal(source_id="src-xyz", title="Find Me")
        store.add_signal(sig)
        result = store.get_signal(sig.id)
        assert result is not None
        assert result.title == "Find Me"


class TestRadarStoreOpportunities:
    """Tests for RadarStore opportunity operations."""

    def test_load_opportunities_empty(self, store: RadarStore) -> None:
        """Loading from a fresh store returns an empty list."""
        result = store.load_opportunities()
        assert result.opportunities == []

    def test_add_opportunity(self, store: RadarStore) -> None:
        """Adding an opportunity persists it."""
        opp = Opportunity(
            title="Test Opportunity",
            summary="A test opportunity",
            opportunity_type=OpportunityType.RISING_TOPIC,
        )
        store.add_opportunity(opp)
        result = store.load_opportunities()
        assert len(result.opportunities) == 1
        assert result.opportunities[0].title == "Test Opportunity"

    def test_get_opportunity(self, store: RadarStore) -> None:
        """Getting an opportunity by id returns it."""
        opp = Opportunity(
            title="Find Me",
            summary="Test",
            opportunity_type=OpportunityType.AUDIENCE_QUESTION,
        )
        store.add_opportunity(opp)
        result = store.get_opportunity(opp.id)
        assert result is not None
        assert result.title == "Find Me"

    def test_update_opportunity_status(self, store: RadarStore) -> None:
        """Updating an opportunity's status persists it."""
        opp = Opportunity(
            title="Status Test",
            summary="Test",
            opportunity_type=OpportunityType.COMPETITOR_MOVE,
            status=OpportunityStatus.NEW,
        )
        store.add_opportunity(opp)
        updated = store.update_opportunity(opp.id, {"status": OpportunityStatus.SAVED})
        assert updated is not None
        assert updated.status == OpportunityStatus.SAVED

    def test_delete_opportunity(self, store: RadarStore) -> None:
        """Deleting an opportunity removes it."""
        opp = Opportunity(
            title="To Delete",
            summary="Test",
            opportunity_type=OpportunityType.NARRATIVE_SHIFT,
        )
        store.add_opportunity(opp)
        deleted = store.delete_opportunity(opp.id)
        assert deleted is True
        assert store.get_opportunity(opp.id) is None

    def test_list_opportunities_filter_by_status(self, store: RadarStore) -> None:
        """Listing opportunities filters by status."""
        for i, status in enumerate([OpportunityStatus.NEW, OpportunityStatus.SAVED, OpportunityStatus.NEW]):
            opp = Opportunity(
                title=f"Opp {i}",
                summary="Test",
                opportunity_type=OpportunityType.PROOF_POINT,
                status=status,
            )
            store.add_opportunity(opp)

        results = store.list_opportunities(status=OpportunityStatus.NEW)
        assert len(results) == 2
        assert all(o.status == OpportunityStatus.NEW for o in results)

    def test_list_opportunities_sorted_by_score(self, store: RadarStore) -> None:
        """Listing opportunities returns them sorted by score descending."""
        for score in [50.0, 90.0, 70.0]:
            opp = Opportunity(
                title=f"Score {score}",
                summary="Test",
                opportunity_type=OpportunityType.RISING_TOPIC,
                total_score=score,
            )
            store.add_opportunity(opp)

        results = store.list_opportunities()
        assert results[0].total_score == 90.0
        assert results[1].total_score == 70.0
        assert results[2].total_score == 50.0

    def test_list_opportunities_limit(self, store: RadarStore) -> None:
        """Listing opportunities respects the limit."""
        for i in range(5):
            opp = Opportunity(
                title=f"Opp {i}",
                summary="Test",
                opportunity_type=OpportunityType.LAUNCH_UPDATE_CHANGE,
                total_score=float(i),
            )
            store.add_opportunity(opp)

        results = store.list_opportunities(limit=3)
        assert len(results) == 3


class TestRadarStoreScores:
    """Tests for RadarStore score operations."""

    def test_upsert_score_new(self, store: RadarStore) -> None:
        """Upserting a score for a new opportunity adds it."""
        opp = Opportunity(
            title="Scored Opp",
            summary="Test",
            opportunity_type=OpportunityType.COMPETITOR_MOVE,
        )
        store.add_opportunity(opp)

        score = OpportunityScore(
            opportunity_id=opp.id,
            strategic_relevance_score=80.0,
            novelty_score=70.0,
            urgency_score=75.0,
            evidence_score=65.0,
            business_value_score=85.0,
            workflow_fit_score=60.0,
            total_score=76.5,
        )
        store.upsert_score(score)

        result = store.get_score(opp.id)
        assert result is not None
        assert result.opportunity_id == opp.id
        assert result.total_score == 76.5

    def test_upsert_score_updates_existing(self, store: RadarStore) -> None:
        """Upserting a score for an existing opportunity replaces it."""
        opp = Opportunity(
            title="Re-score",
            summary="Test",
            opportunity_type=OpportunityType.AUDIENCE_QUESTION,
        )
        store.add_opportunity(opp)

        score1 = OpportunityScore(opportunity_id=opp.id, total_score=50.0)
        store.upsert_score(score1)

        score2 = OpportunityScore(opportunity_id=opp.id, total_score=85.0)
        store.upsert_score(score2)

        result = store.get_score(opp.id)
        assert result is not None
        assert result.total_score == 85.0

        all_scores = store.load_scores()
        assert len(all_scores.scores) == 1


class TestRadarStoreSignalLinks:
    """Tests for RadarStore signal link operations."""

    def test_link_signal_to_opportunity(self, store: RadarStore) -> None:
        """Linking a signal to an opportunity persists the link."""
        opp = Opportunity(
            title="Opp",
            summary="Test",
            opportunity_type=OpportunityType.RISING_TOPIC,
        )
        store.add_opportunity(opp)
        sig = RawSignal(source_id="src-1", title="Signal")
        store.add_signal(sig)

        store.link_signal_to_opportunity(opp.id, sig.id, link_reason="same_topic")

        sig_ids = store.get_signal_ids_for_opportunity(opp.id)
        assert sig.id in sig_ids

    def test_duplicate_link_not_created(self, store: RadarStore) -> None:
        """Linking the same signal twice does not create a duplicate."""
        opp = Opportunity(
            title="Opp",
            summary="Test",
            opportunity_type=OpportunityType.PROOF_POINT,
        )
        store.add_opportunity(opp)
        sig = RawSignal(source_id="src-1", title="Signal")
        store.add_signal(sig)

        store.link_signal_to_opportunity(opp.id, sig.id)
        store.link_signal_to_opportunity(opp.id, sig.id)

        sig_ids = store.get_signal_ids_for_opportunity(opp.id)
        assert sig_ids.count(sig.id) == 1


class TestRadarStoreFeedback:
    """Tests for RadarStore feedback operations."""

    def test_add_feedback(self, store: RadarStore) -> None:
        """Adding feedback persists it."""
        opp = Opportunity(
            title="Feedback Opp",
            summary="Test",
            opportunity_type=OpportunityType.COMPETITOR_MOVE,
        )
        store.add_opportunity(opp)

        from cc_deep_research.radar.models import FeedbackType

        fb = OpportunityFeedback(opportunity_id=opp.id, feedback_type=FeedbackType.SAVED)
        store.add_feedback(fb)

        results = store.get_feedback_for_opportunity(opp.id)
        assert len(results) == 1
        assert results[0].feedback_type == FeedbackType.SAVED

    def test_multiple_feedback_entries(self, store: RadarStore) -> None:
        """Multiple feedback entries can be stored for the same opportunity."""
        opp = Opportunity(
            title="Multi Feedback",
            summary="Test",
            opportunity_type=OpportunityType.NARRATIVE_SHIFT,
        )
        store.add_opportunity(opp)

        from cc_deep_research.radar.models import FeedbackType

        fb1 = OpportunityFeedback(opportunity_id=opp.id, feedback_type=FeedbackType.SAVED)
        fb2 = OpportunityFeedback(opportunity_id=opp.id, feedback_type=FeedbackType.DISMISSED)
        store.add_feedback(fb1)
        store.add_feedback(fb2)

        results = store.get_feedback_for_opportunity(opp.id)
        assert len(results) == 2


class TestRadarStoreWorkflowLinks:
    """Tests for RadarStore workflow link operations."""

    def test_add_workflow_link(self, store: RadarStore) -> None:
        """Adding a workflow link persists it."""
        opp = Opportunity(
            title="Workflow Link",
            summary="Test",
            opportunity_type=OpportunityType.AUDIENCE_QUESTION,
        )
        store.add_opportunity(opp)

        from cc_deep_research.radar.models import FeedbackType

        fb = OpportunityFeedback(opportunity_id=opp.id, feedback_type=FeedbackType.CONVERTED_TO_RESEARCH)
        store.add_feedback(fb)

        link = WorkflowLink(
            opportunity_id=opp.id,
            workflow_type=WorkflowType.RESEARCH_RUN,
            workflow_id="session-abc-123",
        )
        store.add_workflow_link(link)

        results = store.get_workflow_links_for_opportunity(opp.id)
        assert len(results) == 1
        assert results[0].workflow_type == WorkflowType.RESEARCH_RUN
        assert results[0].workflow_id == "session-abc-123"
