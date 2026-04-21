"""Backward-compatible imports for the content generation orchestrator.

The content generation workflow now lives in ``pipeline.py`` and the
``stages/`` package. This module remains as the stable import path for API
routers, tests, and downstream users that still import ``ContentGenOrchestrator``
from ``cc_deep_research.content_gen.orchestrator``.
"""

from __future__ import annotations

from cc_deep_research.content_gen.legacy_orchestrator import (
    ContentGenOrchestrator,
    RunConstraints,
)
from cc_deep_research.content_gen.pipeline import ContentGenPipeline

__all__ = ["ContentGenOrchestrator", "ContentGenPipeline", "RunConstraints"]
