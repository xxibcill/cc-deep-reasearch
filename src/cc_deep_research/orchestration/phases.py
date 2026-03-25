"""Phase-level orchestration helpers for the research workflow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from cc_deep_research.models.analysis import AnalysisResult, StrategyResult, ValidationResult
from cc_deep_research.models.checkpoint import CheckpointOperation, CheckpointPhase
from cc_deep_research.models.search import ResearchDepth, SearchResultItem
from cc_deep_research.monitoring import ResearchMonitor

if TYPE_CHECKING:
    from cc_deep_research.themes import WorkflowConfig


class PhaseRunner:
    """Run monitored workflow phases with consistent telemetry."""

    def __init__(self, *, monitor: ResearchMonitor) -> None:
        self._monitor = monitor
        self._current_phase_id: str | None = None
        self._current_checkpoint_id: str | None = None

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

    @property
    def current_checkpoint_id(self) -> str | None:
        """Return the current checkpoint ID, if any."""
        return self._current_checkpoint_id

    def _map_phase_key_to_checkpoint_phase(self, phase_key: str) -> str:
        """Map internal phase keys to checkpoint phase enum values."""
        mapping = {
            "team_init": CheckpointPhase.TEAM_INIT.value,
            "strategy": CheckpointPhase.STRATEGY.value,
            "query_expansion": CheckpointPhase.QUERY_EXPANSION.value,
            "source_collection": CheckpointPhase.SOURCE_COLLECTION.value,
            "analysis": CheckpointPhase.ANALYSIS.value,
            "deep_analysis": CheckpointPhase.DEEP_ANALYSIS.value,
            "validation": CheckpointPhase.VALIDATION.value,
            "iteration_decision": CheckpointPhase.ITERATION_DECISION.value,
            "iteration_collection": CheckpointPhase.ITERATION_COLLECTION.value,
        }
        return mapping.get(phase_key, phase_key)

    async def run_phase(
        self,
        *,
        phase_hook: Callable[[str, str], None] | None,
        phase_key: str,
        description: str,
        operation: Callable[[], Awaitable[Any]],
        metadata: dict[str, Any] | None = None,
        cancellation_check: Callable[[], None] | None = None,
        input_ref: dict[str, Any] | None = None,
        output_transformer: Callable[[Any], dict[str, Any]] | None = None,
        iteration: int | None = None,
    ) -> Any:
        """Run a monitored phase with full lifecycle events and checkpointing.

        Emits phase.started, runs the operation, then emits phase.completed
        or phase.failed depending on outcome. Uses parent-child correlation
        so child events can be attributed to this phase. Creates a durable
        checkpoint on successful completion.

        Args:
            phase_hook: Optional callback for phase progress.
            phase_key: Unique identifier for the phase.
            description: Human-readable description.
            operation: Async function to execute.
            metadata: Optional additional metadata.
            input_ref: Optional reference to step inputs.
            output_transformer: Optional function to transform output to output_ref.
            iteration: Optional iteration number for iterative phases.

        Returns:
            The result of the operation.

        Raises:
            Exception: Re-raises any exception from the operation.
        """
        self._check_cancelled(cancellation_check)
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

        # Emit initial checkpoint for phase start (if input provided)
        checkpoint_phase = self._map_phase_key_to_checkpoint_phase(phase_key)
        if input_ref is not None:
            self._current_checkpoint_id = self._monitor.emit_checkpoint(
                phase=checkpoint_phase,
                operation=CheckpointOperation.EXECUTE.value,
                iteration=iteration,
                input_ref=input_ref,
                parent_checkpoint_id=self._current_checkpoint_id,
                cause_event_id=phase_event_id,
                metadata={"description": description, **(metadata or {})},
            )

        phase_event = self._monitor.start_operation(
            name=phase_key,
            category="phase",
            description=description,
        )

        try:
            result = await operation()
            self._check_cancelled(cancellation_check)
            self._monitor.end_operation(phase_event, success=True)
            self._monitor.emit_event(
                event_type="phase.completed",
                category="phase",
                name=phase_key,
                status="completed",
                duration_ms=phase_event.duration_ms,
                metadata={"description": description, **(metadata or {})},
            )

            # Finalize checkpoint with output reference
            if self._current_checkpoint_id and output_transformer is not None:
                output_ref = output_transformer(result)
                self._monitor.finalize_checkpoint(
                    self._current_checkpoint_id,
                    output_ref=output_ref,
                    replayable=True,
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
            # Mark checkpoint as not replayable on failure
            if self._current_checkpoint_id:
                self._monitor.finalize_checkpoint(
                    self._current_checkpoint_id,
                    output_ref=None,
                    replayable=False,
                    replayable_reason=f"Phase failed: {type(exc).__name__}",
                )
            raise
        finally:
            # Pop this phase from parent stack
            self._monitor.pop_parent()
            self._current_phase_id = None
            self._current_checkpoint_id = None

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
        cancellation_check: Callable[[], None] | None = None,
        iteration: int | None = None,
        workflow_config: WorkflowConfig | None = None,
    ) -> tuple[AnalysisResult, ValidationResult | None]:
        """Run a single analysis/deep-analysis/validation pass.

        Args:
            phase_hook: Optional callback for phase progress.
            query: Research query.
            depth: Research depth mode.
            strategy: Strategy result from planning phase.
            sources: List of sources to analyze.
            analyze_findings: Callback to run analysis.
            deep_analyze: Callback to run deep analysis.
            validate_research: Callback to run validation.
            log_validation_results: Callback to log validation results.
            cancellation_check: Optional cancellation check callback.
            iteration: Optional iteration number.
            workflow_config: Optional theme workflow configuration.

        Returns:
            Tuple of (analysis_result, validation_result_or_none).
        """
        analysis = await self.run_phase(
            phase_hook=phase_hook,
            phase_key="analysis",
            description="Analyzing findings",
            operation=lambda: analyze_findings(sources, query, strategy),
            cancellation_check=cancellation_check,
            input_ref={
                "query": query,
                "source_count": len(sources),
                "strategy_summary": strategy.summary if hasattr(strategy, "summary") else None,
            },
            output_transformer=lambda result: {
                "finding_count": len(result.key_findings) if hasattr(result, "key_findings") else 0,
                "summary": result.summary if hasattr(result, "summary") else None,
            },
            iteration=iteration,
        )

        # Check if deep analysis should run:
        # 1. Must be in DEEP mode
        # 2. Theme must not skip deep analysis (if theme is configured)
        should_run_deep_analysis = depth == ResearchDepth.DEEP
        if workflow_config is not None and workflow_config.skip_deep_analysis:
            should_run_deep_analysis = False

        if should_run_deep_analysis:
            deep_analysis = await self.run_phase(
                phase_hook=phase_hook,
                phase_key="deep_analysis",
                description="Performing deep multi-pass analysis",
                operation=lambda: deep_analyze(sources, query, analysis),
                cancellation_check=cancellation_check,
                input_ref={
                    "query": query,
                    "source_count": len(sources),
                    "analysis_summary": analysis.summary if hasattr(analysis, "summary") else None,
                },
                output_transformer=lambda result: {
                    "finding_count": len(result.key_findings) if hasattr(result, "key_findings") else 0,
                    "summary": result.summary if hasattr(result, "summary") else None,
                },
                iteration=iteration,
            )
            # Merge deep analysis results, preserving typed nested models
            merged_data = analysis.model_dump(mode="python")
            deep_data = deep_analysis.model_dump(mode="python", exclude_unset=True)
            merged_data.update(deep_data)
            analysis = AnalysisResult.model_validate(merged_data)

        # Check if validation should run:
        # 1. Strategy must enable quality scoring
        # 2. Theme must not skip validation (if theme is configured)
        should_run_validation = strategy.strategy.enable_quality_scoring
        if workflow_config is not None and workflow_config.skip_validation:
            should_run_validation = False

        if not should_run_validation:
            return analysis, None

        validation = await self.run_phase(
            phase_hook=phase_hook,
            phase_key="validation",
            description="Validating research quality",
            operation=lambda: validate_research(query, depth, sources, analysis),
            cancellation_check=cancellation_check,
            input_ref={
                "query": query,
                "source_count": len(sources),
                "analysis_summary": analysis.summary if hasattr(analysis, "summary") else None,
            },
            output_transformer=lambda result: {
                "quality_score": result.quality_score if hasattr(result, "quality_score") else None,
                "needs_follow_up": result.needs_follow_up if hasattr(result, "needs_follow_up") else False,
            },
            iteration=iteration,
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

    def _check_cancelled(self, cancellation_check: Callable[[], None] | None) -> None:
        """Raise when the caller has requested phase execution to stop."""
        if cancellation_check is not None:
            cancellation_check()
