"""Tests for Radar telemetry analytics."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_deep_research.radar.service import RadarService
from cc_deep_research.radar.storage import RadarStore
from cc_deep_research.radar.telemetry import RadarTelemetryStore


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


class TestRadarTelemetryAnalytics:
    """Tests for Radar analytics aggregation."""

    def test_conversion_rates_deduplicate_workflow_links_by_opportunity(
        self,
        service: RadarService,
        store: RadarStore,
    ) -> None:
        """Repeated launches from one opportunity count once in conversion rates."""
        opp = service.create_opportunity("Convert", "Summary", "rising_topic")
        service.update_opportunity_status(opp.id, "acted_on")

        service.link_workflow(opp.id, "brief", "brief-1")
        service.link_workflow(opp.id, "brief", "brief-2")

        analytics = RadarTelemetryStore(store=store).get_analytics()

        assert analytics.conversion_rates["brief"] == 1.0
        assert analytics.conversion_rates["research_run"] == 0.0

    def test_conversion_rates_return_zero_when_nothing_is_acted_on(
        self,
        service: RadarService,
        store: RadarStore,
    ) -> None:
        """Workflow links do not create non-zero rates without acted-on opportunities."""
        opp = service.create_opportunity("Convert", "Summary", "rising_topic")
        service.link_workflow(opp.id, "brief", "brief-1")

        analytics = RadarTelemetryStore(store=store).get_analytics()

        assert analytics.conversion_rates == {
            "research_run": 0.0,
            "brief": 0.0,
            "backlog_item": 0.0,
            "content_pipeline": 0.0,
        }
