"""Phase-level orchestration helpers for the research workflow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from cc_deep_research.models import (
    AnalysisResult,
    ResearchDepth,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor


class PhaseRunner:
    """Run monitored workflow phases with consistent telemetry."""

    def __init__(self, *, monitor: ResearchMonitor) -> None:
        self._monitor = monitor
        self._current_phase_id: str | None = None

    @staticmethod
    def notify_phase(
        phase_hook: Callable[[str, str], None] | None,
        *,
        phase_key: str,
        description: str,
    ) -> None:
        """Emit a phase notification when a hook is configured."""
        if phase_hook is None:
            return
        phase_hook(phase_key, description)

    @property
    def current_phase_id(self) -> str | None:
        """Return the current phase event ID, if any."""
        return self._current_phase_id

    async def run_phase(
        self,
        *,
        phase_hook: Callable[[str, str], None] | None,
        phase_key: str,
        description: str,
        operation: Callable[[], Awaitable[Any]],
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Run a monitored phase with full lifecycle events.

        Emits phase.started, runs the operation, then emits phase.completed
        or phase.failed depending on outcome. Uses parent-child correlation
        so child events can be attributed to this phase.

        Args:
            phase_hook: Optional callback for phase progress.
            phase_key: Unique identifier for the phase.
            description: Human-readable description.
            operation: Async function to execute.
            metadata: Optional additional metadata.

        Returns:
            The result of the operation.

        Raises:
            Exception: Re-raises any exception from the operation.
        """
        self.notify_phase(phase_hook, phase_key=phase_key, description=description)

        # Emit phase.started and get event ID for parent-child correlation
        phase_event_id = self._monitor.emit_event(
            event_type="phase.started",
            category="phase",
            name=phase_key,
            status="started",
            metadata={"description": description, **(metadata or {})},
        )

        # Push this phase as parent for any child events
        self._monitor.push_parent(phase_event_id)
        self._current_phase_id = phase_event_id

        phase_event = self._monitor.start_operation(
            name=phase_key,
            category="phase",
            description=description,
        )

        try:
            result = await operation()
            self._monitor.end_operation(phase_event, success=True)
            self._monitor.emit_event(
                event_type="phase.completed",
                category="phase",
                name=phase_key,
                status="completed",
                duration_ms=phase_event.duration_ms,
                metadata={"description": description, **(metadata or {})},
            )
            return result
        except Exception as exc:
            self._monitor.end_operation(phase_event, success=False)
            self._monitor.emit_event(
                event_type="phase.failed",
                category="phase",
                name=phase_key,
                status="failed",
                duration_ms=phase_event.duration_ms,
                metadata={
                    "description": description,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    **(metadata or {}),
                },
            )
            raise
        finally:
            # Pop this phase from parent stack
            self._monitor.pop_parent()
            self._current_phase_id = None

    async def run_analysis_pass(
        self,
        *,
        phase_hook: Callable[[str, str], None] | None,
        query: str,
        depth: ResearchDepth,
        strategy: StrategyResult,
        sources: list[SearchResultItem],
        analyze_findings: Callable[[list[SearchResultItem], str, StrategyResult], Awaitable[AnalysisResult]],
        deep_analyze: Callable[[list[SearchResultItem], str, AnalysisResult], Awaitable[AnalysisResult]],
        validate_research: Callable[[str, ResearchDepth, list[SearchResultItem], AnalysisResult], Awaitable[ValidationResult]],
        log_validation_results: Callable[[ValidationResult], None],
    ) -> tuple[AnalysisResult, ValidationResult | None]:
        """Run a single analysis/deep-analysis/validation pass."""
        analysis = await self.run_phase(
            phase_hook=phase_hook,
            phase_key="analysis",
            description="Analyzing findings",
            operation=lambda: analyze_findings(sources, query, strategy),
        )

        if depth == ResearchDepth.DEEP:
            deep_analysis = await self.run_phase(
                phase_hook=phase_hook,
                phase_key="deep_analysis",
                description="Performing deep multi-pass analysis",
                operation=lambda: deep_analyze(sources, query, analysis),
            )
            # Merge deep analysis results, preserving typed nested models
            merged_data = analysis.model_dump(mode="python")
            deep_data = deep_analysis.model_dump(mode="python", exclude_unset=True)
            merged_data.update(deep_data)
            analysis = AnalysisResult.model_validate(merged_data)

        if not strategy.strategy.enable_quality_scoring:
            return analysis, None

        validation = await self.run_phase(
            phase_hook=phase_hook,
            phase_key="validation",
            description="Validating research quality",
            operation=lambda: validate_research(query, depth, sources, analysis),
        )
        log_validation_results(validation)
        return analysis, validation

    def log_session_summary(
        self,
        *,
        source_count: int,
        finding_count: int,
        validation: ValidationResult | None,
    ) -> None:
        """Log the final research-session summary."""
        self._monitor.section("Summary")
        self._monitor.log(f"Total sources: {source_count}")
        self._monitor.log(f"Key findings: {finding_count}")
        if validation is not None:
            self._monitor.log(f"Quality score: {validation.quality_score:.2f}")
