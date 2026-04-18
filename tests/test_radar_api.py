"""Tests for Radar API routes using FastAPI test client with temporary storage."""

from __future__ import annotations

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cc_deep_research.event_router import EventRouter
from cc_deep_research.radar.router import register_radar_routes
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


@pytest.fixture
def mock_event_router() -> Generator[MagicMock, None, None]:
    """Return a mock EventRouter that tracks published events."""
    router = MagicMock()
    router.is_active.return_value = True
    router.publish.return_value = None
    yield router


@pytest.fixture
def app(service: RadarService, mock_event_router: MagicMock) -> Generator[FastAPI, None, None]:
    """Create a test FastAPI app with Radar routes registered."""
    application = FastAPI()
    application.state.dashboard_runtime = MagicMock()
    application.state.dashboard_runtime.event_router = mock_event_router

    register_radar_routes(application, mock_event_router, service=service)

    yield application


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Return a test client for the app."""
    with TestClient(app) as c:
        yield c


class TestRadarSourcesAPI:
    """Tests for Radar source API endpoints."""

    def test_create_source(self, client: TestClient) -> None:
        """POST /api/radar/sources creates a source and returns it."""
        response = client.post(
            "/api/radar/sources",
            json={
                "source_type": "news",
                "label": "TechCrunch",
                "url_or_identifier": "https://techcrunch.com/feed",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["label"] == "TechCrunch"
        assert data["source_type"] == "news"
        assert "id" in data
        assert data["id"].startswith("src-")

    def test_create_source_with_cadence(self, client: TestClient) -> None:
        """POST /api/radar/sources respects scan_cadence."""
        response = client.post(
            "/api/radar/sources",
            json={
                "source_type": "blog",
                "label": "My Blog",
                "url_or_identifier": "http://myblog.com/rss",
                "scan_cadence": "1h",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scan_cadence"] == "1h"

    def test_list_sources(self, client: TestClient) -> None:
        """GET /api/radar/sources returns all sources."""
        # Create two sources
        client.post(
            "/api/radar/sources",
            json={"source_type": "news", "label": "Source 1", "url_or_identifier": "http://s1.com"},
        )
        client.post(
            "/api/radar/sources",
            json={"source_type": "blog", "label": "Source 2", "url_or_identifier": "http://s2.com"},
        )

        response = client.get("/api/radar/sources")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["items"]) == 2

    def test_list_sources_filter_by_status(self, client: TestClient, service: RadarService) -> None:
        """GET /api/radar/sources can filter by status."""
        from cc_deep_research.radar.models import SourceStatus

        r1 = client.post(
            "/api/radar/sources",
            json={"source_type": "news", "label": "Active", "url_or_identifier": "http://active.com"},
        )
        r2 = client.post(
            "/api/radar/sources",
            json={"source_type": "news", "label": "Inactive", "url_or_identifier": "http://inactive.com"},
        )

        # Update second source to inactive
        inactive_id = r2.json()["id"]
        service._store.update_source(inactive_id, {"status": SourceStatus.INACTIVE})

        response = client.get("/api/radar/sources", params={"status": "active"})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["label"] == "Active"


class TestRadarOpportunitiesAPI:
    """Tests for Radar opportunity API endpoints."""

    def test_list_opportunities(self, client: TestClient, service: RadarService) -> None:
        """GET /api/radar/opportunities returns all opportunities."""
        service.create_opportunity("Opp 1", "Summary 1", "rising_topic")
        service.create_opportunity("Opp 2", "Summary 2", "competitor_move")

        response = client.get("/api/radar/opportunities")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_list_opportunities_filter_by_type(self, client: TestClient, service: RadarService) -> None:
        """GET /api/radar/opportunities filters by opportunity_type."""
        service.create_opportunity("Type A", "Summary", "competitor_move")
        service.create_opportunity("Type B", "Summary", "rising_topic")

        response = client.get("/api/radar/opportunities", params={"opportunity_type": "rising_topic"})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["opportunity_type"] == "rising_topic"

    def test_list_opportunities_filter_by_status(self, client: TestClient, service: RadarService) -> None:
        """GET /api/radar/opportunities filters by status."""
        opp1 = service.create_opportunity("New Opp", "Summary", "rising_topic")
        service.create_opportunity("Saved Opp", "Summary", "rising_topic")
        service.update_opportunity_status(opp1.id, "saved")

        response = client.get("/api/radar/opportunities", params={"status": "new"})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["status"] == "new"

    def test_get_opportunity_detail(self, client: TestClient, service: RadarService) -> None:
        """GET /api/radar/opportunities/{id} returns full detail."""
        opp = service.create_opportunity("Test Detail", "Summary", "rising_topic")

        response = client.get(f"/api/radar/opportunities/{opp.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["opportunity"]["id"] == opp.id
        assert data["score"] is None
        assert data["signals"] == []
        assert data["feedback"] == []

    def test_get_opportunity_detail_not_found(self, client: TestClient) -> None:
        """GET /api/radar/opportunities/{id} returns 404 for non-existent id."""
        response = client.get("/api/radar/opportunities/opp-does-not-exist")
        assert response.status_code == 404
        assert response.json()["error"] == "Opportunity not found"

    def test_update_opportunity_status(self, client: TestClient, service: RadarService) -> None:
        """POST /api/radar/opportunities/{id}/status updates status."""
        opp = service.create_opportunity("Status Test", "Summary", "rising_topic")
        assert opp.status.value == "new"

        response = client.post(
            f"/api/radar/opportunities/{opp.id}/status",
            json={"status": "saved"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"

    def test_update_opportunity_status_not_found(self, client: TestClient) -> None:
        """POST /api/radar/opportunities/{id}/status returns 404 for non-existent."""
        response = client.post(
            "/api/radar/opportunities/opp-does-not-exist/status",
            json={"status": "saved"},
        )
        assert response.status_code == 404
        assert response.json()["error"] == "Opportunity not found"

    def test_record_feedback(self, client: TestClient, service: RadarService) -> None:
        """POST /api/radar/opportunities/{id}/feedback records feedback."""
        opp = service.create_opportunity("Feedback Test", "Summary", "rising_topic")

        response = client.post(
            f"/api/radar/opportunities/{opp.id}/feedback",
            json={"feedback_type": "saved"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["opportunity_id"] == opp.id
        assert data["feedback_type"] == "saved"

    def test_record_feedback_with_metadata(self, client: TestClient, service: RadarService) -> None:
        """POST /api/radar/opportunities/{id}/feedback accepts metadata."""
        opp = service.create_opportunity("Metadata", "Summary", "rising_topic")

        response = client.post(
            f"/api/radar/opportunities/{opp.id}/feedback",
            json={
                "feedback_type": "acted_on",
                "metadata": {"converted_to": "research_run", "session_id": "abc"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["metadata"]["converted_to"] == "research_run"

    def test_record_feedback_not_found(self, client: TestClient) -> None:
        """POST /api/radar/opportunities/{id}/feedback returns 404 for non-existent."""
        response = client.post(
            "/api/radar/opportunities/opp-does-not-exist/feedback",
            json={"feedback_type": "saved"},
        )
        assert response.status_code == 404
        assert response.json()["error"] == "Opportunity not found"
