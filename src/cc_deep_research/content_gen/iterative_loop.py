"""Reusable evaluation loop for iterative content generation quality improvement."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from cc_deep_research.content_gen.models import (
    IterationState,
    QualityEvaluation,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class LoopConfig:
    """Configuration slice needed by the evaluation loop.

    Decouples from the full Config/ContentGenConfig so the loop
    can be used without pulling in the entire config hierarchy.
    """

    max_iterations: int = 3
    quality_threshold: float = 0.75
    convergence_threshold: float = 0.05

    def validate(self) -> None:
        """Validate configuration bounds.

        Raises:
            ValueError: If any configuration value is out of valid range.
        """
        if not isinstance(self.max_iterations, int) or self.max_iterations < 1:
            raise ValueError(f"max_iterations must be >= 1, got {self.max_iterations}")
        if self.max_iterations > 10:
            raise ValueError(f"max_iterations must be <= 10, got {self.max_iterations}")
        if not (0.0 <= self.quality_threshold <= 1.0):
            raise ValueError(f"quality_threshold must be between 0.0 and 1.0, got {self.quality_threshold}")
        if not (0.0 <= self.convergence_threshold <= 0.5):
            raise ValueError(f"convergence_threshold must be between 0.0 and 0.5, got {self.convergence_threshold}")


@dataclass
class LoopResult(Generic[T]):
    """Final output of the evaluation loop."""

    artifact: T
    iteration_state: IterationState


# Callable type aliases
Producer = Callable[[str], Awaitable[T]]
Evaluator = Callable[[T, int, str], Awaitable[QualityEvaluation]]
FeedbackInjector = Callable[[T, QualityEvaluation], None] | None


async def run_evaluation_loop(
    *,
    producer: Producer[T],
    evaluator: Evaluator[T],
    config: LoopConfig,
    feedback_injector: FeedbackInjector[T] = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> LoopResult[T]:
    """Run an iterative produce-evaluate loop until quality threshold or convergence.

    Args:
        producer: Async callable that takes a feedback string and returns an artifact.
        evaluator: Async callable that takes (artifact, iteration_number, previous_feedback)
                   and returns a QualityEvaluation.
        config: Loop parameters (max iterations, thresholds).
        feedback_injector: Optional callback to mutate the artifact with evaluation feedback
                           between iterations. If None, feedback is only communicated via the
                           producer's feedback string argument.
        progress_callback: Optional callback for progress reporting (iteration_index, label).

    Returns:
        LoopResult with the final artifact and full iteration state history.
    """
    config.validate()
    iter_state = IterationState(max_iterations=config.max_iterations)
    previous_feedback = ""
    artifact: T | None = None

    while iter_state.current_iteration <= iter_state.max_iterations:
        iteration = iter_state.current_iteration
        logger.info("Evaluation loop iteration %d/%d", iteration, config.max_iterations)
        if progress_callback:
            progress_callback(-1, f"Iteration {iteration}/{config.max_iterations}")

        # Produce
        artifact = await producer(previous_feedback)

        # Evaluate
        quality_eval = await evaluator(artifact, iteration, previous_feedback)
        iter_state.quality_history.append(quality_eval)
        iter_state.latest_feedback = format_feedback(quality_eval)

        # Check stop conditions
        if should_stop(quality_eval, iter_state, config):
            iter_state.is_converged = True
            iter_state.convergence_reason = quality_eval.rationale
            break

        # Prepare next iteration
        previous_feedback = iter_state.latest_feedback
        if feedback_injector:
            feedback_injector(artifact, quality_eval)
        iter_state.current_iteration += 1

    return LoopResult(artifact=artifact, iteration_state=iter_state)  # type: ignore[arg-type]


def should_stop(
    quality_eval: QualityEvaluation,
    iter_state: IterationState,
    config: LoopConfig,
) -> bool:
    """Decide whether to stop iterating."""
    if quality_eval.passes_threshold:
        return True
    if iter_state.current_iteration >= iter_state.max_iterations:
        return True
    if len(iter_state.quality_history) >= 2:
        prev_score = iter_state.quality_history[-2].overall_quality_score
        improvement = quality_eval.overall_quality_score - prev_score
        if improvement < config.convergence_threshold:
            return True
    return False


def format_feedback(quality_eval: QualityEvaluation) -> str:
    """Format evaluation into a feedback string for the next iteration."""
    parts: list[str] = []
    if quality_eval.critical_issues:
        parts.append("Critical issues:")
        parts.extend(f"- {i}" for i in quality_eval.critical_issues)
    if quality_eval.improvement_suggestions:
        parts.append("Improvement suggestions:")
        parts.extend(f"- {s}" for s in quality_eval.improvement_suggestions)
    if quality_eval.rationale:
        parts.append(f"Rationale: {quality_eval.rationale}")
    return "\n".join(parts)
