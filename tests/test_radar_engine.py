"""Tests for RadarEngine: clustering, scoring, freshness, and ingest cycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from cc_deep_research.radar.engine import (
    FreshnessManager,
    RadarEngine,
    ScoreCalculator,
    SignalCluster,
    SignalClusterer,
)
from cc_deep_research.radar.models import (
    FreshnessState,
    Opportunity,
    OpportunityScore,
    OpportunityStatus,
    OpportunityType,
    RadarSource,
    RawSignal,
    SourceStatus,
    SourceType,
)
from cc_deep_research.radar.scanner import (
    RSSScanner,
    compute_content_hash,
    is_due_for_scan,
    parse_cadence,
    strip_html,
)
from cc_deep_research.radar.storage import RadarStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_radar_dir(tmp_path: Path) -> Path:
    return tmp_path / "radar"


@pytest.fixture
def store(temp_radar_dir: Path) -> RadarStore:
    return RadarStore(radar_dir=temp_radar_dir)


@pytest.fixture
def engine(store: RadarStore) -> RadarEngine:
    return RadarEngine(store=store)


# ---------------------------------------------------------------------------
# Cadence tests
# ---------------------------------------------------------------------------


class TestParseCadence:
    def test_valid_hourly_cadences(self) -> None:
        assert parse_cadence("1h") == timedelta(hours=1)
        assert parse_cadence("6h") == timedelta(hours=6)
        assert parse_cadence("12h") == timedelta(hours=12)

    def test_valid_daily_cadences(self) -> None:
        assert parse_cadence("1d") == timedelta(days=1)
        assert parse_cadence("2d") == timedelta(days=2)
        assert parse_cadence("7d") == timedelta(days=7)

    def test_valid_minute_cadences(self) -> None:
        assert parse_cadence("5m") == timedelta(minutes=5)
        assert parse_cadence("15m") == timedelta(minutes=15)

    def test_invalid_cadence_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_cadence("invalid")
        with pytest.raises(ValueError):
            parse_cadence("99z")


class TestIsDueForScan:
    def test_active_source_never_scanned_is_due(self) -> None:
        src = RadarSource(
            source_type=SourceType.NEWS,
            label="Test",
            url_or_identifier="http://test.com",
            last_scanned_at=None,
        )
        assert is_due_for_scan(src) is True

    def test_inactive_source_not_due(self) -> None:
        src = RadarSource(
            source_type=SourceType.NEWS,
            label="Test",
            url_or_identifier="http://test.com",
            status=SourceStatus.INACTIVE,
            last_scanned_at=datetime.now(tz=UTC).isoformat(),
        )
        assert is_due_for_scan(src) is False

    def test_source_scanned_recently_not_due(self) -> None:
        recent = datetime.now(tz=UTC) - timedelta(minutes=30)
        src = RadarSource(
            source_type=SourceType.NEWS,
            label="Test",
            url_or_identifier="http://test.com",
            scan_cadence="6h",
            last_scanned_at=recent.isoformat(),
        )
        assert is_due_for_scan(src) is False

    def test_source_scanned_long_ago_is_due(self) -> None:
        old = datetime.now(tz=UTC) - timedelta(hours=7)
        src = RadarSource(
            source_type=SourceType.NEWS,
            label="Test",
            url_or_identifier="http://test.com",
            scan_cadence="6h",
            last_scanned_at=old.isoformat(),
        )
        assert is_due_for_scan(src) is True


# ---------------------------------------------------------------------------
# HTML stripping tests
# ---------------------------------------------------------------------------


class TestStripHtml:
    def test_strips_simple_tags(self) -> None:
        assert strip_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_strips_complex_html(self) -> None:
        html = '<a href="http://example.com">Click <strong>here</strong></a>'
        assert strip_html(html) == "Click here"

    def test_handles_none(self) -> None:
        assert strip_html(None) == ""

    def test_normalizes_whitespace(self) -> None:
        assert strip_html("Hello  \n\n   World") == "Hello World"


# ---------------------------------------------------------------------------
# Content hash tests
# ---------------------------------------------------------------------------


class TestComputeContentHash:
    def test_same_content_same_hash(self) -> None:
        h1 = compute_content_hash("Test Title", "http://example.com")
        h2 = compute_content_hash("Test Title", "http://example.com")
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        h1 = compute_content_hash("Title A", "http://example.com")
        h2 = compute_content_hash("Title B", "http://example.com")
        assert h1 != h2

    def test_none_url_is_handled(self) -> None:
        h = compute_content_hash("Title", None)
        assert len(h) == 16


# ---------------------------------------------------------------------------
# RSS Scanner type checks
# ---------------------------------------------------------------------------


class TestRSSScannerCanHandle:
    def test_handles_news_blog_changelog(self) -> None:
        scanner = RSSScanner()
        assert scanner.can_handle(SourceType.NEWS) is True
        assert scanner.can_handle(SourceType.BLOG) is True
        assert scanner.can_handle(SourceType.CHANGELOG) is True

    def test_does_not_handle_forum_social(self) -> None:
        scanner = RSSScanner()
        assert scanner.can_handle(SourceType.FORUM) is False
        assert scanner.can_handle(SourceType.SOCIAL) is False


# ---------------------------------------------------------------------------
# Signal clusterer tests
# ---------------------------------------------------------------------------


class TestSignalClusterer:
    def test_extract_keywords(self) -> None:
        kws = SignalClusterer._extract_keywords(
            "New AI Features Launched by Competitor",
            "Analysis of the latest release",
        )
        assert "new" in kws
        assert "features" in kws
        assert "launched" in kws
        assert "competitor" in kws
        assert "analysis" in kws
        assert "the" not in kws  # filtered out

    def test_jaccard_similarity(self) -> None:
        s1 = {"ai", "machine", "learning", "launch"}
        s2 = {"ai", "machine", "learning", "new"}
        sim = SignalClusterer._jaccard_similarity(s1, s2)
        assert sim == 0.6  # 3/5

    def test_cosine_similarity(self) -> None:
        s1 = {"ai", "machine", "learning"}
        s2 = {"ai", "machine", "learning", "new"}
        sim = SignalClusterer._cosine_similarity(s1, s2)
        # 3 / sqrt(3*4) = 3 / sqrt(12) ≈ 0.866
        assert sim > 0.85

    def test_cluster_signals_single(self) -> None:
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Breaking: Competitor releases new AI product",
                summary="Analysis of competitor move",
                published_at=datetime.now(tz=UTC).isoformat(),
            )
        ]
        clusterer = SignalClusterer()
        clusters = clusterer.cluster_signals(signals)
        assert len(clusters) == 1
        assert clusters[0].signal_count == 1

    def test_cluster_signals_similar_grouped(self) -> None:
        now = datetime.now(tz=UTC)
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Competitor launches new feature",
                summary="Analysis of new feature",
                published_at=now.isoformat(),
            ),
            RawSignal(
                id="sig2",
                source_id="src1",
                title="Competitor feature update",
                summary="Competitor's new feature analyzed",
                published_at=(now - timedelta(hours=1)).isoformat(),
            ),
            RawSignal(
                id="sig3",
                source_id="src1",
                title="Something about cooking recipes",
                summary="Best recipe for pasta",
                published_at=(now - timedelta(hours=2)).isoformat(),
            ),
        ]
        clusterer = SignalClusterer()
        clusters = clusterer.cluster_signals(signals)
        # First two should cluster together (competitor/feature overlap)
        assert len(clusters) >= 2


# ---------------------------------------------------------------------------
# Score calculator tests
# ---------------------------------------------------------------------------


class TestScoreCalculator:
    def test_strategic_relevance_high(self) -> None:
        calc = ScoreCalculator()
        opp = Opportunity(
            title="Competitor Market Strategy Shift",
            summary="Analysis of competitor move in the market",
            opportunity_type=OpportunityType.COMPETITOR_MOVE,
        )
        signals = []
        score = calc._score_strategic_relevance(opp, signals)
        assert score >= 70  # contains competitor, market, strategy

    def test_strategic_relevance_low(self) -> None:
        calc = ScoreCalculator()
        opp = Opportunity(
            title="Random Topic",
            summary="Something unrelated",
            opportunity_type=OpportunityType.RISING_TOPIC,
        )
        score = calc._score_strategic_relevance(opp, [])
        assert score < 50

    def test_novelty_recent(self) -> None:
        calc = ScoreCalculator()
        now = datetime.now(tz=UTC)
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Recent news",
                published_at=now.isoformat(),
            )
        ]
        score = calc._score_novelty(signals)
        assert score >= 90

    def test_novelty_old(self) -> None:
        calc = ScoreCalculator()
        old = datetime.now(tz=UTC) - timedelta(days=5)
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Old news",
                published_at=old.isoformat(),
            )
        ]
        score = calc._score_novelty(signals)
        assert score <= 35

    def test_evidence_more_signals_higher(self) -> None:
        calc = ScoreCalculator()
        signals5 = [
            RawSignal(id="1", source_id="src1", title="Test"),
            RawSignal(id="2", source_id="src1", title="Test"),
            RawSignal(id="3", source_id="src1", title="Test"),
            RawSignal(id="4", source_id="src1", title="Test"),
            RawSignal(id="5", source_id="src1", title="Test"),
        ]
        signals1 = [RawSignal(id="1", source_id="src1", title="Test")]
        cluster5 = SignalCluster(signal_ids=["1", "2", "3", "4", "5"])
        cluster1 = SignalCluster(signal_ids=["1"])

        assert calc._score_evidence(signals5, cluster5) > calc._score_evidence(signals1, cluster1)

    def test_business_value_by_type(self) -> None:
        calc = ScoreCalculator()
        competitor_move = Opportunity(
            title="Test", summary="Test", opportunity_type=OpportunityType.COMPETITOR_MOVE
        )
        recurring = Opportunity(
            title="Test", summary="Test", opportunity_type=OpportunityType.RECURRING_PATTERN
        )
        assert calc._score_business_value(competitor_move) > calc._score_business_value(recurring)

    def test_workflow_fit_more_complete_higher(self) -> None:
        calc = ScoreCalculator()
        complete = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.RISING_TOPIC,
            why_it_matters="Because it is",
            recommended_action="Do something",
        )
        incomplete = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.RISING_TOPIC,
        )
        complete_signals = [
            RawSignal(id="sig1", source_id="src1", title="Test", url="http://example.com"),
        ]
        empty_signals: list[RawSignal] = []
        assert calc._score_workflow_fit(complete, complete_signals) > calc._score_workflow_fit(
            incomplete, empty_signals
        )

    def test_calculate_returns_score_and_explanation(self) -> None:
        calc = ScoreCalculator()
        opp = Opportunity(
            title="Competitor releases new feature",
            summary="Analysis of competitor move",
            opportunity_type=OpportunityType.COMPETITOR_MOVE,
            why_it_matters="Strategic importance",
            recommended_action="Review and respond",
        )
        now = datetime.now(tz=UTC)
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Competitor launches feature",
                summary="Analysis",
                published_at=now.isoformat(),
            ),
            RawSignal(
                id="sig2",
                source_id="src1",
                title="Competitor feature update",
                summary="More analysis",
                published_at=(now - timedelta(hours=1)).isoformat(),
            ),
        ]
        cluster = SignalCluster(
            signal_ids=["sig1", "sig2"],
            opportunity_type=OpportunityType.COMPETITOR_MOVE,
            keywords=["competitor", "feature", "launch"],
        )
        score, explanation = calc.calculate(opp, signals, cluster)

        assert isinstance(score, OpportunityScore)
        assert score.total_score >= 0
        assert score.total_score <= 100
        assert len(explanation) > 20
        assert "Total score:" in explanation


# ---------------------------------------------------------------------------
# Freshness manager tests
# ---------------------------------------------------------------------------


class TestFreshnessManager:
    def test_new_opportunity_is_new_freshness(self) -> None:
        mgr = FreshnessManager()
        now = datetime.now(tz=UTC)
        opp = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.RISING_TOPIC,
            first_detected_at=now.isoformat(),
        )
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Test",
                published_at=(now - timedelta(days=3)).isoformat(),
            )
        ]
        state = mgr.compute_freshness_state(opp, signals)
        assert state == FreshnessState.NEW

    def test_recent_signal_is_fresh(self) -> None:
        mgr = FreshnessManager()
        now = datetime.now(tz=UTC)
        opp = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.RISING_TOPIC,
            first_detected_at=(now - timedelta(days=2)).isoformat(),
        )
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Test",
                published_at=(now - timedelta(hours=2)).isoformat(),
            )
        ]
        state = mgr.compute_freshness_state(opp, signals)
        assert state == FreshnessState.FRESH

    def test_old_signal_is_stale(self) -> None:
        mgr = FreshnessManager()
        now = datetime.now(tz=UTC)
        opp = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.RISING_TOPIC,
            first_detected_at=(now - timedelta(days=5)).isoformat(),
        )
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Test",
                published_at=(now - timedelta(days=2)).isoformat(),
            )
        ]
        state = mgr.compute_freshness_state(opp, signals)
        assert state == FreshnessState.STALE

    def test_very_old_signal_is_expired(self) -> None:
        mgr = FreshnessManager()
        now = datetime.now(tz=UTC)
        opp = Opportunity(
            title="Test",
            summary="Test",
            opportunity_type=OpportunityType.RISING_TOPIC,
            first_detected_at=(now - timedelta(days=10)).isoformat(),
        )
        signals = [
            RawSignal(
                id="sig1",
                source_id="src1",
                title="Test",
                published_at=(now - timedelta(days=4)).isoformat(),
            )
        ]
        state = mgr.compute_freshness_state(opp, signals)
        assert state == FreshnessState.EXPIRED


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


class TestEngineDeduplication:
    def test_duplicate_content_hash_filtered(self, engine: RadarEngine) -> None:
        existing = RawSignal(
            id="sig-existing",
            source_id="src1",
            title="Existing Article",
            url="http://example.com/1",
            content_hash="abcd1234",
        )
        engine._store.add_signal(existing)

        new_signals = [
            RawSignal(
                id="sig-new",
                source_id="src1",
                title="Existing Article",
                url="http://example.com/1",
                content_hash="abcd1234",
            )
        ]

        unique = engine.deduplicate_signals(new_signals)
        assert len(unique) == 0

    def test_duplicate_external_id_filtered(self, engine: RadarEngine) -> None:
        existing = RawSignal(
            id="sig-existing",
            source_id="src1",
            title="Existing",
            external_id="guid-123",
        )
        engine._store.add_signal(existing)

        new_signals = [
            RawSignal(
                id="sig-new",
                source_id="src1",
                title="Same but different title",
                external_id="guid-123",
            )
        ]

        unique = engine.deduplicate_signals(new_signals)
        assert len(unique) == 0

    def test_duplicate_external_id_filtered_within_same_batch(self, engine: RadarEngine) -> None:
        new_signals = [
            RawSignal(
                id="sig-new-1",
                source_id="src1",
                title="First version",
                external_id="guid-123",
                content_hash="hash-1",
            ),
            RawSignal(
                id="sig-new-2",
                source_id="src1",
                title="Second version",
                external_id="guid-123",
                content_hash="hash-2",
            ),
        ]

        unique = engine.deduplicate_signals(new_signals)
        assert len(unique) == 1
        assert unique[0].id == "sig-new-1"

    def test_different_source_different_content_not_dupe(self, engine: RadarEngine) -> None:
        # Different content from different sources = not duplicates
        existing = RawSignal(
            id="sig-existing",
            source_id="src1",
            title="Article A",
            content_hash="hash-a",
        )
        engine._store.add_signal(existing)

        new_signals = [
            RawSignal(
                id="sig-new",
                source_id="src2",
                title="Article B",
                content_hash="hash-b",
            )
        ]

        unique = engine.deduplicate_signals(new_signals)
        assert len(unique) == 1


# ---------------------------------------------------------------------------
# End-to-end ingest tests
# ---------------------------------------------------------------------------


class TestEngineIngestCycle:
    def test_ingest_with_no_sources(self, engine: RadarEngine) -> None:
        result = engine.run_ingest_cycle()
        assert result["signals_scanned"] == 0
        assert result["signals_new"] == 0
        assert result["clusters_created"] == 0
        assert result["opportunities_created"] == 0

    def test_ingest_creates_opportunity(
        self,
        engine: RadarEngine,
        store: RadarStore,
    ) -> None:
        # Create a source
        src = RadarSource(
            source_type=SourceType.NEWS,
            label="Test News",
            url_or_identifier="http://test.com/feed",
            status=SourceStatus.ACTIVE,
        )
        store.add_source(src)

        # Mock the scanner to return fake signals
        now = datetime.now(tz=UTC)
        fake_signals = [
            RawSignal(
                id="sig1",
                source_id=src.id,
                title="Competitor launches new AI feature",
                summary="Analysis of competitor move",
                url="http://test.com/1",
                published_at=now.isoformat(),
                content_hash="hash1",
            ),
            RawSignal(
                id="sig2",
                source_id=src.id,
                title="Competitor AI feature update",
                summary="Follow-up analysis",
                url="http://test.com/2",
                published_at=(now - timedelta(hours=1)).isoformat(),
                content_hash="hash2",
            ),
        ]

        with patch.object(engine._scanner, "scan_due_sources", return_value=fake_signals):
            result = engine.run_ingest_cycle()

        assert result["signals_scanned"] == 2
        assert result["signals_new"] == 2
        assert result["clusters_created"] >= 1

        # Check opportunity was created
        opportunities = store.load_opportunities().opportunities
        assert len(opportunities) >= 1

        opp = opportunities[0]
        assert opp.total_score > 0
        assert opp.status == OpportunityStatus.NEW

        # Check score exists
        score = store.get_score(opp.id)
        assert score is not None
        assert score.total_score > 0

    def test_duplicate_signals_do_not_create_duplicate_opportunities(
        self,
        engine: RadarEngine,
        store: RadarStore,
    ) -> None:
        src = RadarSource(
            source_type=SourceType.NEWS,
            label="Test",
            url_or_identifier="http://test.com/feed",
            status=SourceStatus.ACTIVE,
        )
        store.add_source(src)

        now = datetime.now(tz=UTC)
        sig = RawSignal(
            id="sig1",
            source_id=src.id,
            title="Competitor launches feature",
            summary="Analysis",
            url="http://test.com/1",
            published_at=now.isoformat(),
            content_hash="unique-hash",
        )

        # First ingest
        with patch.object(engine._scanner, "scan_due_sources", return_value=[sig]):
            engine.run_ingest_cycle()

        opportunities_first = store.load_opportunities().opportunities
        count_first = len(opportunities_first)

        # Second ingest with same signal (should be deduplicated)
        with patch.object(engine._scanner, "scan_due_sources", return_value=[sig]):
            engine.run_ingest_cycle()

        opportunities_second = store.load_opportunities().opportunities
        count_second = len(opportunities_second)

        assert count_second == count_first


# ---------------------------------------------------------------------------
# Rescore tests
# ---------------------------------------------------------------------------


class TestRescore:
    def test_rescore_updates_score(
        self,
        engine: RadarEngine,
        store: RadarStore,
    ) -> None:
        # Create an opportunity with a low score
        opp = Opportunity(
            title="Test Opportunity",
            summary="Test",
            opportunity_type=OpportunityType.RISING_TOPIC,
        )
        store.add_opportunity(opp)

        now = datetime.now(tz=UTC)
        sig = RawSignal(
            id="sig1",
            source_id="src1",
            title="New signal",
            published_at=now.isoformat(),
        )
        store.add_signal(sig)
        store.link_signal_to_opportunity(opp.id, sig.id)

        # Rescore
        updated = engine.rescore_opportunity(opp.id)

        assert updated is not None
        assert updated.total_score > 0

        # Score should also be persisted
        score = store.get_score(opp.id)
        assert score is not None
        assert score.total_score > 0

    def test_rescore_nonexistent_returns_none(self, engine: RadarEngine) -> None:
        result = engine.rescore_opportunity("nonexistent-id")
        assert result is None
