"""Pure helper functions for orchestration workflows."""

from __future__ import annotations

from typing import Any

from cc_deep_research.models import AnalysisResult, QueryFamily, StrategyResult, ValidationResult


def normalize_query_families(
    *,
    original_query: str,
    strategy: StrategyResult,
    raw_families: list[QueryFamily | str],
) -> list[QueryFamily]:
    """Normalize expansion output into typed query-family models."""
    normalized_families: list[QueryFamily] = []
    for item in raw_families:
        if isinstance(item, QueryFamily):
            normalized_families.append(item)
            continue

        family = "baseline" if item == original_query else "baseline"
        normalized_families.append(
            QueryFamily(
                query=str(item),
                family=family,
                intent_tags=[family, strategy.strategy.intent],
            )
        )
    return normalized_families


def build_follow_up_queries(
    *,
    query: str,
    analysis: AnalysisResult | dict[str, Any],
    validation: ValidationResult | dict[str, Any] | None,
    enable_iterative_search: bool,
) -> list[str]:
    """Build deduplicated follow-up queries for an iterative pass."""
    analysis_result = AnalysisResult.model_validate(analysis)
    validation_result = (
        ValidationResult.model_validate(validation) if validation is not None else None
    )

    if not enable_iterative_search:
        return []

    if validation_result and not validation_result.needs_follow_up:
        return []

    follow_up_queries: list[str] = []
    if validation_result:
        follow_up_queries.extend(validation_result.follow_up_queries)

    if not follow_up_queries:
        for gap in analysis_result.normalized_gaps():
            follow_up_queries.extend(gap.suggested_queries)
            follow_up_queries.append(f"{query} {gap.gap_description}")

    deduplicated: list[str] = []
    seen: set[str] = set()
    for candidate in follow_up_queries:
        normalized = candidate.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduplicated.append(candidate.strip())
    return deduplicated[:8]


def decompose_parallel_tasks(queries: list[str]) -> list[dict[str, str]]:
    """Decompose queries into parallel research tasks."""
    return [
        {
            "task_id": f"task-{index}",
            "query": query,
        }
        for index, query in enumerate(queries, start=1)
    ]
