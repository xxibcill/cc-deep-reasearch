"""Standalone scripting run logic extracted from legacy orchestrator.

This module provides `ScriptingRunService`, which replaces the deprecated
`ContentGenOrchestrator` for standalone scripting and iterative-loop execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models import IterationState, QualityEvaluation, ScriptingContext

if TYPE_CHECKING:
    from cc_deep_research.config import Config

# Re-export IterationState so callers don't need to import from models
__all__ = ["ScriptingRunService", "IterationState"]


class ScriptingRunService:
    """Standalone scripting executor with iterative refinement.

    Replaces the deprecated ``ContentGenOrchestrator`` for standalone scripting
    flows. Supports single-pass and iterative modes.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Single-pass scripting
    # ------------------------------------------------------------------

    async def run_scripting(
        self,
        raw_idea: str,
        progress_callback=None,
        *,
        llm_route: str | None = None,
    ) -> ScriptingContext:
        """Run the full 10-step scripting pipeline (single-pass)."""
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent

        agent = ScriptingAgent(self._config, llm_route=llm_route)
        return await agent.run_pipeline(raw_idea, progress_callback=progress_callback)

    async def run_scripting_from_step(
        self,
        ctx: ScriptingContext,
        step: int,
        progress_callback=None,
        *,
        llm_route: str | None = None,
    ) -> ScriptingContext:
        """Resume the scripting pipeline from a specific step."""
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent

        agent = ScriptingAgent(self._config, llm_route=llm_route)
        return await agent.run_from_step(ctx, step, progress_callback=progress_callback)

    # ------------------------------------------------------------------
    # Iterative scripting
    # ------------------------------------------------------------------

    async def run_scripting_iterative(
        self,
        raw_idea: str,
        progress_callback=None,
        max_iterations: int | None = None,
        *,
        llm_route: str | None = None,
    ) -> tuple[ScriptingContext, IterationState]:
        """Run the scripting pipeline inside an evaluation loop.

        Iteration 1 runs the full pipeline. Subsequent iterations inject
        feedback into research_context and re-run from step 5 (hooks) onward.
        """
        from cc_deep_research.content_gen.agents.quality_evaluator import (
            QualityEvaluatorAgent,
        )
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent
        from cc_deep_research.content_gen.iterative_loop import (
            LoopConfig,
            run_evaluation_loop,
        )

        agent = ScriptingAgent(self._config, llm_route=llm_route)
        evaluator_agent = QualityEvaluatorAgent(self._config)
        threshold = self._config.content_gen.quality_threshold
        latest_ctx: ScriptingContext | None = None

        async def producer(feedback: str) -> ScriptingContext:
            nonlocal latest_ctx
            if latest_ctx is None:
                latest_ctx = await agent.run_pipeline(
                    raw_idea,
                    progress_callback=progress_callback,
                    iteration=1,
                )
            else:
                if feedback:
                    existing = latest_ctx.research_context or ""
                    latest_ctx.research_context = f"{feedback}\n\n{existing}"
                latest_ctx = await agent.run_from_step(
                    latest_ctx,
                    5,
                    progress_callback=progress_callback,
                    iteration=latest_ctx.step_traces[-1].iteration + 1
                    if latest_ctx.step_traces
                    else 2,
                )
            return latest_ctx

        async def evaluator(
            artifact: ScriptingContext, iteration: int, prev_feedback: str
        ) -> QualityEvaluation:
            return await evaluator_agent.evaluate_scripting(
                scripting=artifact,
                iteration_number=iteration,
                quality_threshold=threshold,
                previous_feedback=prev_feedback,
            )

        loop_config = LoopConfig(
            max_iterations=max_iterations or self._config.content_gen.max_iterations,
            quality_threshold=threshold,
            convergence_threshold=self._config.content_gen.convergence_threshold,
        )

        result = await run_evaluation_loop(
            producer=producer,
            evaluator=evaluator,
            config=loop_config,
            progress_callback=progress_callback,
        )
        return result.artifact, result.iteration_state
