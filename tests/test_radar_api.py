"""Tests for Radar API routes using FastAPI test client with temporary storage."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import PipelineContext
from cc_deep_research.content_gen.progress import PipelineRunJobRegistry
from cc_deep_research.models import ResearchSession
from cc_deep_research.radar.router import register_radar_routes
from cc_deep_research.radar.service import RadarService
from cc_deep_research.radar.storage import RadarStore
from cc_deep_research.research_runs.jobs import ResearchRunJobRegistry
from cc_deep_research.research_runs.models import (
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunResult,
)


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
    router.publish = AsyncMock(return_value=None)
    yield router


@pytest.fixture
def app(
    service: RadarService,
    mock_event_router: MagicMock,
    temp_radar_dir: Path,
) -> Generator[FastAPI, None, None]:
    """Create a test FastAPI app with Radar routes registered."""
    application = FastAPI()
    application.state.dashboard_runtime = SimpleNamespace(
        event_router=mock_event_router,
        jobs=ResearchRunJobRegistry(),
        pipeline_jobs=PipelineRunJobRegistry(path=temp_radar_dir / "pipeline-jobs"),
    )

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

    def test_list_sources_invalid_status_returns_422(self, client: TestClient) -> None:
        """GET /api/radar/sources rejects invalid status filters."""
        response = client.get("/api/radar/sources", params={"status": "bogus"})
        assert response.status_code == 422


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

    @pytest.mark.parametrize(
        ("params"),
        [
            {"status": "bogus"},
            {"opportunity_type": "bogus"},
            {"freshness": "bogus"},
        ],
    )
    def test_list_opportunities_invalid_filters_return_422(
        self,
        client: TestClient,
        params: dict[str, str],
    ) -> None:
        """GET /api/radar/opportunities rejects invalid filters."""
        response = client.get("/api/radar/opportunities", params=params)
        assert response.status_code == 422

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


class TestRadarWorkflowLaunchAPI:
    """Tests for Radar workflow launch endpoints."""

    def test_launch_research_starts_background_job(
        self,
        client: TestClient,
        app: FastAPI,
        service: RadarService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Launching research should queue a browser-style research job."""
        opp = service.create_opportunity(
            "AI pricing shifts",
            "Pricing trends across AI tools",
            "rising_topic",
            why_it_matters="Customers are re-evaluating vendors.",
        )

        class FakeResearchRunService:
            def run(self, request, *, on_session_started=None, **_kwargs) -> ResearchRunResult:
                if on_session_started is not None:
                    on_session_started("session-radar-123")
                return ResearchRunResult(
                    session=ResearchSession(
                        session_id="session-radar-123",
                        query=request.query,
                    ),
                    report=ResearchRunReport(
                        format=ResearchOutputFormat.MARKDOWN,
                        content="# report",
                        media_type="text/markdown",
                    ),
                )

        monkeypatch.setattr(
            "cc_deep_research.research_runs.service.ResearchRunService",
            FakeResearchRunService,
        )

        response = client.post(f"/api/radar/opportunities/{opp.id}/launch-research")

        assert response.status_code == 202
        data = response.json()
        assert data["opportunity_id"] == opp.id
        assert data["research_run_id"].startswith("run-")
        assert data["status"] in {"queued", "running"}
        assert data["session_id"] is None

        job = app.state.dashboard_runtime.jobs.get_job(data["research_run_id"])
        assert job is not None
        assert job.request.query.startswith("AI pricing shifts")

        updated = service._store.get_opportunity(opp.id)
        assert updated is not None
        assert updated.status.value == "acted_on"

        links = service._store.get_workflow_links_for_opportunity(opp.id)
        assert [link.workflow_id for link in links] == [data["research_run_id"]]

    def test_launch_content_pipeline_starts_real_pipeline_job(
        self,
        client: TestClient,
        app: FastAPI,
        service: RadarService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Launching a content pipeline should create a tracked pipeline job."""
        opp = service.create_opportunity(
            "Video essay on AI pricing",
            "Explain the new pricing psychology for AI buyers",
            "rising_topic",
            why_it_matters="The market is shifting quickly.",
        )

        class FakeOrchestrator:
            def __init__(self, _config: Config) -> None:
                pass

            async def run_full_pipeline(
                self,
                theme: str,
                *,
                from_stage: int = 0,
                to_stage: int | None = None,
                progress_callback=None,
                stage_completed_callback=None,
                run_constraints=None,
                **_kwargs,
            ) -> PipelineContext:
                assert theme == "Video essay on AI pricing"
                assert from_stage == 0
                assert to_stage is not None
                assert run_constraints is not None
                if progress_callback is not None:
                    progress_callback(0, "Loading strategy memory")
                ctx = PipelineContext(theme=theme, current_stage=to_stage)
                if stage_completed_callback is not None:
                    stage_completed_callback(0, "completed", "", ctx)
                return ctx

        monkeypatch.setattr("cc_deep_research.config.load_config", lambda: Config())
        monkeypatch.setattr(
            "cc_deep_research.content_gen.pipeline.ContentGenPipeline",
            FakeOrchestrator,
        )

        response = client.post(f"/api/radar/opportunities/{opp.id}/launch-content-pipeline")

        assert response.status_code == 202
        data = response.json()
        assert data["opportunity_id"] == opp.id
        assert data["pipeline_id"]
        assert data["status"] in {"queued", "running"}

        job = app.state.dashboard_runtime.pipeline_jobs.get_job(data["pipeline_id"])
        assert job is not None
        assert job.theme == "Video essay on AI pricing"

        updated = service._store.get_opportunity(opp.id)
        assert updated is not None
        assert updated.status.value == "acted_on"

        links = service._store.get_workflow_links_for_opportunity(opp.id)
        assert [link.workflow_id for link in links] == [data["pipeline_id"]]
