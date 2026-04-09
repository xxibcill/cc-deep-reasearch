"""Central retry and timeout policy for local orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from cc_deep_research.config import Config
from cc_deep_research.models.planning import ResearchSubtask

DEFAULT_CONTENT_FETCH_TIMEOUT_SECONDS = 15.0

_NON_RETRIABLE_EXCEPTIONS = (
    AttributeError,
    KeyError,
    NotImplementedError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True, slots=True)
class OrchestrationTimeoutPolicy:
    """Resolved timeout values used by the local orchestrator."""

    team_timeout_seconds: float
    researcher_timeout_seconds: float
    content_fetch_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class ParallelCollectionPolicy:
    """Resolved policy for parallel source collection."""

    timeouts: OrchestrationTimeoutPolicy
    fallback_to_sequential: bool


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Explicit retry decision for a subtask failure."""

    should_retry: bool
    attempt: int
    max_attempts: int
    retries_remaining: int
    reason_code: str


class ParallelCollectionError(RuntimeError):
    """Raised when parallel collection cannot produce a usable result set."""


class ParallelCollectionTimeoutError(TimeoutError):
    """Raised when every parallel collection task times out."""


def build_orchestration_timeout_policy(config: Config) -> OrchestrationTimeoutPolicy:
    """Resolve timeout settings from the small set of supported config paths."""
    researcher_timeout = float(config.search_team.researcher_timeout)
    return OrchestrationTimeoutPolicy(
        team_timeout_seconds=float(config.search_team.timeout_seconds),
        researcher_timeout_seconds=researcher_timeout,
        content_fetch_timeout_seconds=min(
            DEFAULT_CONTENT_FETCH_TIMEOUT_SECONDS,
            researcher_timeout,
        ),
    )


def build_parallel_collection_policy(config: Config) -> ParallelCollectionPolicy:
    """Resolve the timeout and fallback policy for parallel collection."""
    return ParallelCollectionPolicy(
        timeouts=build_orchestration_timeout_policy(config),
        fallback_to_sequential=config.search_team.fallback_to_sequential,
    )


def decide_subtask_retry(
    *,
    task: ResearchSubtask,
    attempt: int,
    error: Exception,
) -> RetryDecision:
    """Return the explicit retry decision for a failed task attempt."""
    max_attempts = task.max_retries + 1
    retries_remaining = max(0, max_attempts - attempt)

    if isinstance(error, _NON_RETRIABLE_EXCEPTIONS):
        return RetryDecision(
            should_retry=False,
            attempt=attempt,
            max_attempts=max_attempts,
            retries_remaining=retries_remaining,
            reason_code="non_retriable_error",
        )

    if attempt >= max_attempts:
        return RetryDecision(
            should_retry=False,
            attempt=attempt,
            max_attempts=max_attempts,
            retries_remaining=0,
            reason_code="retry_exhausted",
        )

    reason_code = "timeout_retry" if isinstance(error, TimeoutError) else "retry_scheduled"
    return RetryDecision(
        should_retry=True,
        attempt=attempt,
        max_attempts=max_attempts,
        retries_remaining=retries_remaining,
        reason_code=reason_code,
    )


__all__ = [
    "DEFAULT_CONTENT_FETCH_TIMEOUT_SECONDS",
    "OrchestrationTimeoutPolicy",
    "ParallelCollectionError",
    "ParallelCollectionPolicy",
    "ParallelCollectionTimeoutError",
    "RetryDecision",
    "build_orchestration_timeout_policy",
    "build_parallel_collection_policy",
    "decide_subtask_retry",
]
