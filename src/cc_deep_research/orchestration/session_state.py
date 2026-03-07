"""Session-scoped metadata state for the research orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    ResearchDepth,
    StrategyResult,
    ValidationResult,
)


@dataclass
class OrchestratorSessionState:
    """Track session-scoped provider and degradation metadata."""

    configured_providers: list[str]
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    execution_degradations: list[str] = field(default_factory=list)
    used_parallel_collection: bool = False

    def reset(self, configured_providers: list[str]) -> None:
        """Reset state for a new session."""
        self.configured_providers = list(configured_providers)
        self.provider_metadata = {
            "configured": list(configured_providers),
            "available": [],
            "warnings": [],
        }
        self.execution_degradations = []
        self.used_parallel_collection = False

    def note_execution_degradation(self, reason: str) -> None:
        """Record a session-level degradation reason once."""
        if reason not in self.execution_degradations:
            self.execution_degradations.append(reason)

    def set_provider_metadata(self, *, available: list[str], warnings: list[str]) -> None:
        """Record provider-resolution metadata for the current session."""
        self.provider_metadata = {
            "configured": list(self.configured_providers),
            "available": list(available),
            "warnings": list(warnings),
        }
        for warning in warnings:
            self.note_execution_degradation(warning)

    def mark_parallel_collection_used(self) -> None:
        """Mark that the session used parallel collection."""
        self.used_parallel_collection = True

    def build_metadata(
        self,
        *,
        depth: ResearchDepth,
        strategy: StrategyResult,
        analysis: AnalysisResult,
        validation: ValidationResult | None,
        iteration_history: list[IterationHistoryRecord],
        parallel_requested: bool,
    ) -> dict[str, Any]:
        """Build the stable session metadata contract for persisted sessions."""
        deep_analysis_complete = analysis.deep_analysis_complete
        deep_analysis_method = analysis.analysis_method
        deep_analysis_requested = depth == ResearchDepth.DEEP
        deep_analysis_reason: str | None = None

        if deep_analysis_requested and not deep_analysis_complete:
            deep_analysis_reason = "Deep analysis produced no deep-analysis output."
        elif deep_analysis_requested and deep_analysis_method == "shallow_keyword":
            deep_analysis_reason = (
                "Deep analysis used shallow fallback output because source content was limited."
            )

        if deep_analysis_reason:
            self.note_execution_degradation(deep_analysis_reason)

        return {
            "strategy": strategy.model_dump(mode="python"),
            "analysis": analysis.model_dump(mode="python"),
            "validation": validation.model_dump(mode="python") if validation else {},
            "iteration_history": [
                record.model_dump(mode="python") for record in iteration_history
            ],
            "providers": self.provider_metadata,
            "execution": {
                "parallel_requested": parallel_requested,
                "parallel_used": self.used_parallel_collection,
                "degraded": bool(self.execution_degradations),
                "degraded_reasons": self.execution_degradations,
            },
            "deep_analysis": {
                "requested": deep_analysis_requested,
                "completed": deep_analysis_complete,
                "reason": deep_analysis_reason,
            },
        }
