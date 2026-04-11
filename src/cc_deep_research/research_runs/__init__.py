"""Reusable contracts and helpers for research runs."""

from __future__ import annotations

from typing import Any

from cc_deep_research.themes import ResearchTheme

from .models import (
    ResearchArtifactKind,
    ResearchOutputFormat,
    ResearchRunArtifact,
    ResearchRunCancelled,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
    ResearchWorkflow,
)
from .options import apply_research_request_config_overrides

__all__ = [
    "AsyncioResearchRunExecutionAdapter",
    "PreparedResearchRun",
    "ResearchArtifactKind",
    "ResearchRunCancelled",
    "ResearchOutputFormat",
    "ResearchRunArtifact",
    "ResearchRunExecutionAdapter",
    "ResearchRunReport",
    "ResearchRunRequest",
    "ResearchRunResult",
    "ResearchRunStatus",
    "ResearchRunService",
    "ResearchTheme",
    "ResearchWorkflow",
    "apply_research_request_config_overrides",
    "materialize_research_run_output",
]


def __getattr__(name: str) -> Any:
    """Lazily expose helpers that would otherwise create import cycles."""
    if name == "materialize_research_run_output":
        from .output import materialize_research_run_output

        return materialize_research_run_output
    if name in {
        "AsyncioResearchRunExecutionAdapter",
        "PreparedResearchRun",
        "ResearchRunExecutionAdapter",
        "ResearchRunService",
    }:
        from .service import (
            AsyncioResearchRunExecutionAdapter,
            PreparedResearchRun,
            ResearchRunExecutionAdapter,
            ResearchRunService,
        )

        return {
            "AsyncioResearchRunExecutionAdapter": AsyncioResearchRunExecutionAdapter,
            "PreparedResearchRun": PreparedResearchRun,
            "ResearchRunExecutionAdapter": ResearchRunExecutionAdapter,
            "ResearchRunService": ResearchRunService,
        }[name]
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
