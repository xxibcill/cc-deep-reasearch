"""Tests for the reusable evaluation loop wrapper."""

from __future__ import annotations

import pytest

from cc_deep_research.content_gen.iterative_loop import (
    LoopConfig,
    LoopResult,
    format_feedback,
    run_evaluation_loop,
    should_stop,
)
from cc_deep_research.content_gen.models import (
    IterationState,
    QualityEvaluation,
)


def _make_eval(
    *,
    score: float = 0.5,
    passes: bool = False,
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
    rationale: str = "",
    iteration: int = 1,
) -> QualityEvaluation:
    return QualityEvaluation(
        overall_quality_score=score,
        passes_threshold=passes,
        critical_issues=issues or [],
        improvement_suggestions=suggestions or [],
        rationale=rationale,
        iteration_number=iteration,
    )


# ---------------------------------------------------------------------------
# should_stop
# ---------------------------------------------------------------------------


def test_should_stop_when_passes_threshold():
    ev = _make_eval(passes=True)
    state = IterationState(max_iterations=3)
    assert should_stop(ev, state, LoopConfig()) is True


def test_should_stop_at_max_iterations():
    ev = _make_eval(score=0.3)
    state = IterationState(current_iteration=3, max_iterations=3)
    assert should_stop(ev, state, LoopConfig()) is True


def test_should_stop_on_convergence():
    config = LoopConfig(convergence_threshold=0.1)
    state = IterationState(current_iteration=2, max_iterations=5)
    prev = _make_eval(score=0.55, iteration=1)
    current = _make_eval(score=0.6, iteration=2)
    state.quality_history.append(prev)
    state.quality_history.append(current)
    assert should_stop(current, state, config) is True


def test_should_not_stop_when_improving():
    config = LoopConfig(convergence_threshold=0.05)
    state = IterationState(current_iteration=2, max_iterations=5)
    prev = _make_eval(score=0.5, iteration=1)
    current = _make_eval(score=0.7, iteration=2)
    state.quality_history.append(prev)
    state.quality_history.append(current)
    assert should_stop(current, state, config) is False


def test_should_not_stop_single_iteration_no_threshold():
    ev = _make_eval(score=0.3)
    state = IterationState(current_iteration=1, max_iterations=5)
    assert should_stop(ev, state, LoopConfig()) is False


# ---------------------------------------------------------------------------
# format_feedback
# ---------------------------------------------------------------------------


def test_format_feedback_with_issues_and_suggestions():
    ev = _make_eval(
        issues=["weak hook", "too long"],
        suggestions=["tighten opening", "cut filler"],
        rationale="needs work",
    )
    text = format_feedback(ev)
    assert "Critical issues:" in text
    assert "- weak hook" in text
    assert "Improvement suggestions:" in text
    assert "- tighten opening" in text
    assert "Rationale: needs work" in text


def test_format_feedback_empty():
    ev = _make_eval()
    assert format_feedback(ev) == ""


# ---------------------------------------------------------------------------
# run_evaluation_loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_exits_on_threshold():
    """Loop runs once and exits when evaluation passes threshold."""
    call_count = 0

    async def producer(feedback: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"artifact-{call_count}"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        return _make_eval(score=0.9, passes=True, iteration=iteration)

    result = await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=3),
    )

    assert call_count == 1
    assert result.artifact == "artifact-1"
    assert result.iteration_state.is_converged
    assert len(result.iteration_state.quality_history) == 1


@pytest.mark.asyncio
async def test_loop_runs_to_max_iterations():
    """Loop runs max_iterations times when threshold is never met."""
    call_count = 0

    async def producer(feedback: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"artifact-{call_count}"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        # Improving score prevents convergence but never passes threshold
        score = 0.3 + iteration * 0.1
        return _make_eval(score=score, passes=False, iteration=iteration)

    result = await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=3, convergence_threshold=0.01),
    )

    assert call_count == 3
    assert len(result.iteration_state.quality_history) == 3


@pytest.mark.asyncio
async def test_loop_stops_on_convergence():
    """Loop stops early when improvement is below convergence threshold."""
    scores = [0.4, 0.45]
    call_count = 0

    async def producer(feedback: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"artifact-{call_count}"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        score = scores[iteration - 1] if iteration <= len(scores) else 0.46
        return _make_eval(score=score, passes=False, iteration=iteration)

    result = await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=5, convergence_threshold=0.1),
    )

    assert call_count == 2
    assert result.iteration_state.is_converged


@pytest.mark.asyncio
async def test_feedback_passed_to_producer():
    """Feedback from evaluation is passed to producer on next iteration."""
    received_feedbacks: list[str] = []

    async def producer(feedback: str) -> str:
        received_feedbacks.append(feedback)
        return "artifact"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        return _make_eval(
            score=0.3 if iteration < 2 else 0.9,
            passes=iteration >= 2,
            suggestions=["improve X"],
            iteration=iteration,
        )

    await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=3),
    )

    # First call gets empty string, second gets the formatted feedback
    assert received_feedbacks[0] == ""
    assert "improve X" in received_feedbacks[1]


@pytest.mark.asyncio
async def test_feedback_injector_called():
    """Optional feedback_injector is called with artifact and evaluation."""
    injections: list[tuple[str, QualityEvaluation]] = []

    async def producer(feedback: str) -> str:
        return "artifact"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        return _make_eval(
            score=0.3 if iteration < 2 else 0.9,
            passes=iteration >= 2,
            issues=["issue-A"],
            iteration=iteration,
        )

    def injector(artifact: str, evaluation: QualityEvaluation) -> None:
        injections.append((artifact, evaluation))

    await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=3),
        feedback_injector=injector,
    )

    # Injector called once (after iteration 1, not after iteration 2 which stops)
    assert len(injections) == 1
    assert injections[0][0] == "artifact"
    assert injections[0][1].critical_issues == ["issue-A"]


@pytest.mark.asyncio
async def test_progress_callback_receives_iterations():
    """Progress callback fires once per iteration."""
    progress_calls: list[tuple[int, str]] = []

    async def producer(feedback: str) -> str:
        return "artifact"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        return _make_eval(score=0.9, passes=True, iteration=iteration)

    await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=3),
        progress_callback=lambda idx, label: progress_calls.append((idx, label)),
    )

    assert len(progress_calls) == 1
    assert progress_calls[0] == (-1, "Iteration 1/3")


@pytest.mark.asyncio
async def test_result_contains_full_quality_history():
    """LoopResult has all evaluations in quality_history."""
    async def producer(feedback: str) -> str:
        return "artifact"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        # Improve by 0.2 each iteration so convergence doesn't trigger,
        # pass threshold on iteration 3
        score = 0.1 + iteration * 0.2
        return _make_eval(
            score=score,
            passes=iteration >= 3,
            iteration=iteration,
        )

    result = await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=5, convergence_threshold=0.01),
    )

    assert len(result.iteration_state.quality_history) == 3
    assert result.iteration_state.quality_history[0].iteration_number == 1
    assert result.iteration_state.quality_history[2].iteration_number == 3
