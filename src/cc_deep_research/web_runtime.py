"""Typed accessors for process-local FastAPI runtime dependencies."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI

from cc_deep_research.content_gen.progress import PipelineRunJobRegistry
from cc_deep_research.event_router import EventRouter
from cc_deep_research.research_runs.jobs import (
    BackgroundJobRegistry,
    ResearchRunJobRegistry,
)


def get_event_router(app: FastAPI) -> EventRouter:
    """Return the shared event router from app runtime state."""
    return cast(EventRouter, app.state.dashboard_runtime.event_router)


def get_job_registry(app: FastAPI) -> ResearchRunJobRegistry:
    """Return the shared research job registry from app runtime state."""
    return cast(ResearchRunJobRegistry, app.state.dashboard_runtime.jobs)


def get_background_job_registry(app: FastAPI) -> BackgroundJobRegistry:
    """Return the shared generic background job registry from app runtime state."""
    return cast(BackgroundJobRegistry, app.state.dashboard_runtime.background_jobs)


def get_pipeline_job_registry(app: FastAPI) -> PipelineRunJobRegistry:
    """Return the shared content pipeline job registry from app runtime state."""
    return cast(PipelineRunJobRegistry, app.state.dashboard_runtime.pipeline_jobs)


__all__ = [
    "get_background_job_registry",
    "get_event_router",
    "get_job_registry",
    "get_pipeline_job_registry",
]
