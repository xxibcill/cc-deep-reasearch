"""Backward-compatible import layer for the content generation orchestrator.

Normal pipeline execution now routes through ``ContentGenPipeline`` in
``pipeline.py``.  This module exists as the stable import path for API routers,
tests, and downstream code that imports from
``cc_deep_research.content_gen.orchestrator``.

``ContentGenOrchestrator`` is deprecated — its public methods are preserved
as a thin compatibility facade that delegates to ``ContentGenPipeline``.
New code should use ``ContentGenPipeline`` directly.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.legacy_orchestrator import (
    ContentGenOrchestrator as _LegacyOrchestrator,
)
from cc_deep_research.content_gen.legacy_orchestrator import (
    RunConstraints,
)
from cc_deep_research.content_gen.pipeline import ContentGenPipeline

if TYPE_CHECKING:
    from cc_deep_research.config import Config

__all__ = ["ContentGenOrchestrator", "ContentGenPipeline", "RunConstraints"]


# -----------------------------------------------------------------------
# Deprecation shim
# -----------------------------------------------------------------------


class ContentGenOrchestrator(_LegacyOrchestrator):
    """Deprecated: use ``ContentGenPipeline`` directly.

    This class is retained as a backward-compatible shim.  All pipeline
    execution now routes through ``ContentGenPipeline``.
    """

    def __init__(self, config: Config) -> None:
        warnings.warn(
            "ContentGenOrchestrator is deprecated. "
            "Use ContentGenPipeline from cc_deep_research.content_gen.pipeline directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(config)
