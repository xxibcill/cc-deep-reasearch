"""Session assembly helpers for the research orchestrator."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    ResearchDepth,
    ResearchSession,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)


class SessionBuilder:
    """Assemble the final research session from workflow outputs."""

    def build(
        self,
        *,
        session_id: str,
        query: str,
        depth: ResearchDepth,
        sources: list[SearchResultItem],
        started_at: datetime,
        strategy: StrategyResult,
        analysis: AnalysisResult,
        validation: ValidationResult | None,
        iteration_history: list[IterationHistoryRecord],
        build_metadata: Callable[..., dict[str, Any]],
    ) -> ResearchSession:
        """Build a fully populated research session."""
        return ResearchSession(
            session_id=session_id,
            query=query,
            depth=depth,
            sources=sources,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            metadata=build_metadata(
                depth=depth,
                strategy=strategy,
                analysis=analysis,
                validation=validation,
                iteration_history=iteration_history,
            ),
        )
