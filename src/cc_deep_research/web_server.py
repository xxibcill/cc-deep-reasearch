"""FastAPI web server for real-time monitoring dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cc_deep_research.config import (
    ConfigOverrideError,
    ConfigPatchError,
    ConfigPatchErrorResponse,
    ConfigPatchRequest,
    build_config_response,
    update_config,
)
from cc_deep_research.content_gen._services import build_content_gen_services
from cc_deep_research.content_gen.maintenance_workflow import MaintenanceScheduler
from cc_deep_research.content_gen.progress import (
    PipelineRunJobRegistry,
)
from cc_deep_research.content_gen.router import register_content_gen_routes
from cc_deep_research.event_router import EventRouter
from cc_deep_research.radar.router import register_radar_routes
from cc_deep_research.reporting import ReportGenerator
from cc_deep_research.research_runs.jobs import ResearchRunJobRegistry
from cc_deep_research.research_runs.service import ResearchRunService
from cc_deep_research.web_server_routes import (
    register_knowledge_routes,
    register_misc_routes,
    register_research_run_routes,
    register_session_routes,
    register_websocket_routes,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DashboardBackendRuntime:
    """Process-local runtime dependencies owned by the FastAPI app."""

    event_router: EventRouter
    jobs: ResearchRunJobRegistry
    pipeline_jobs: PipelineRunJobRegistry
    maintenance_scheduler: MaintenanceScheduler | None = None

    async def start(self) -> None:
        """Start shared realtime infrastructure."""
        await self.event_router.start()
        if self.maintenance_scheduler is not None:
            self.maintenance_scheduler.start()

    async def stop(self) -> None:
        """Stop shared infrastructure and cancel in-flight jobs."""
        await self.jobs.cancel_all()
        await self.pipeline_jobs.cancel_all()
        if self.maintenance_scheduler is not None:
            self.maintenance_scheduler.stop()
        await self.event_router.stop()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle."""
    runtime = get_backend_runtime(app)
    await runtime.start()
    yield
    await runtime.stop()


def create_app(
    event_router: EventRouter | None = None,
    job_registry: ResearchRunJobRegistry | None = None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        event_router: Optional EventRouter for WebSocket broadcasting.
        job_registry: Optional in-process run registry for browser-started jobs.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="CC Deep Research Monitoring",
        description="Real-time monitoring dashboard for CC Deep Research",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.dashboard_runtime = DashboardBackendRuntime(
        event_router=event_router or EventRouter(),
        jobs=job_registry or ResearchRunJobRegistry(),
        pipeline_jobs=PipelineRunJobRegistry(),
    )

    # Initialize maintenance scheduler if configured
    maintenance_scheduler: MaintenanceScheduler | None = None
    try:
        from cc_deep_research.config import load_config
        config = load_config()
        interval_hours = getattr(config.content_gen, "maintenance_interval_hours", 0.0)
        if interval_hours > 0:
            maintenance_scheduler = MaintenanceScheduler(config=config, interval_hours=interval_hours)
            app.state.dashboard_runtime.maintenance_scheduler = maintenance_scheduler
    except Exception:
        logger.exception("Failed to initialize maintenance scheduler")

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules
    register_routes(app)

    # Content generation routes
    runtime = get_backend_runtime(app)
    config = load_config()
    services = build_content_gen_services(
        config=config,
        event_router=runtime.event_router,
        job_registry=runtime.pipeline_jobs,
    )
    register_content_gen_routes(app, runtime.event_router, runtime.pipeline_jobs, services)

    # Radar routes
    register_radar_routes(app, runtime.event_router)

    # Knowledge graph routes
    register_knowledge_routes(app)

    return app


# Global app instance
_app: FastAPI | None = None


def get_app() -> FastAPI:
    """Get or create the global FastAPI app instance."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


def get_backend_runtime(app: FastAPI) -> DashboardBackendRuntime:
    """Return the typed dashboard runtime stored on the app."""
    return cast(DashboardBackendRuntime, app.state.dashboard_runtime)


def get_event_router(app: FastAPI) -> EventRouter:
    """Return the shared event router from app runtime state."""
    return get_backend_runtime(app).event_router


def get_job_registry(app: FastAPI) -> ResearchRunJobRegistry:
    """Return the shared job registry from app runtime state."""
    return get_backend_runtime(app).jobs


def get_pipeline_job_registry(app: FastAPI) -> PipelineRunJobRegistry:
    """Return the shared pipeline job registry from app runtime state."""
    return get_backend_runtime(app).pipeline_jobs


def register_routes(app: FastAPI) -> None:
    """Register all API routes.

    Args:
        app: The FastAPI application instance.
    """

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {
            "message": "CC Deep Research Monitoring API",
            "version": "1.0.0",
        }

    @app.get("/api/config")
    async def get_config() -> JSONResponse:
        """Return persisted and effective config for the settings page."""
        response = build_config_response()
        return JSONResponse(content=response.model_dump(mode="json"))

    @app.patch("/api/config")
    async def patch_config(request: ConfigPatchRequest) -> JSONResponse:
        """Apply and persist a partial config update."""
        try:
            response = update_config(
                request.updates,
                save_overridden_fields=request.save_overridden_fields,
            )
        except ConfigOverrideError as error:
            payload = ConfigPatchErrorResponse(
                error=error.message,
                conflicts=error.conflicts,
            )
            return JSONResponse(
                content=payload.model_dump(mode="json"),
                status_code=409,
            )
        except ConfigPatchError as error:
            payload = ConfigPatchErrorResponse(
                error=error.message,
                fields=error.fields,
            )
            return JSONResponse(
                content=payload.model_dump(mode="json"),
                status_code=400,
            )

        return JSONResponse(content=response.model_dump(mode="json"))

    # Register extracted route modules
    register_research_run_routes(app)
    register_session_routes(app)
    register_misc_routes(app)
    register_websocket_routes(app)


def start_server(
    host: str = "localhost",
    port: int = 8000,
    event_router: EventRouter | None = None,
    job_registry: ResearchRunJobRegistry | None = None,
) -> None:
    """Start the FastAPI server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        event_router: Optional EventRouter for WebSocket broadcasting.
        job_registry: Optional process-local registry for browser-started runs.
    """
    import uvicorn

    app = create_app(event_router=event_router, job_registry=job_registry)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        ws="websockets-sansio",
    )


__all__ = [
    "DashboardBackendRuntime",
    "create_app",
    "get_backend_runtime",
    "get_app",
    "get_event_router",
    "get_job_registry",
    "get_pipeline_job_registry",
    "register_routes",
    "start_server",
    # Re-exported for backward compatibility with tests
    "ReportGenerator",
    "ResearchRunService",
]
