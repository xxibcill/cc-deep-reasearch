"""Session-scoped metadata state for the research orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    ResearchDepth,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)


@dataclass
class LLMRouteRecord:
    """Record of a single LLM route assignment or change."""

    agent_id: str
    transport: str
    provider: str
    model: str
    source: str = "config"  # config, planner, fallback
    timestamp: str | None = None


@dataclass
class LLMRouteUsageStats:
    """Statistics for LLM route usage during a session."""

    request_count: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error_count: int = 0
    total_latency_ms: int = 0


@dataclass
class OrchestratorSessionState:
    """Track session-scoped provider and degradation metadata."""

    configured_providers: list[str]
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    execution_degradations: list[str] = field(default_factory=list)
    used_parallel_collection: bool = False
    # LLM route tracking
    llm_planned_routes: dict[str, LLMRouteRecord] = field(default_factory=dict)
    llm_actual_routes: dict[str, LLMRouteRecord] = field(default_factory=dict)
    llm_route_usage: dict[str, LLMRouteUsageStats] = field(default_factory=dict)
    llm_fallback_events: list[dict[str, Any]] = field(default_factory=list)

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
        self.llm_planned_routes = {}
        self.llm_actual_routes = {}
        self.llm_route_usage = {}
        self.llm_fallback_events = []

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

    def set_llm_planned_route(
        self,
        agent_id: str,
        transport: str,
        provider: str,
        model: str,
        source: str = "planner",
        timestamp: str | None = None,
    ) -> None:
        """Record a planned LLM route for an agent.

        Args:
            agent_id: The agent identifier.
            transport: The transport type (claude_cli, openrouter_api, etc.).
            provider: The provider type (claude, openrouter, etc.).
            model: The model identifier.
            source: Where the route came from (planner, config).
            timestamp: Optional timestamp for the route assignment.
        """
        self.llm_planned_routes[agent_id] = LLMRouteRecord(
            agent_id=agent_id,
            transport=transport,
            provider=provider,
            model=model,
            source=source,
            timestamp=timestamp,
        )

    def set_llm_actual_route(
        self,
        agent_id: str,
        transport: str,
        provider: str,
        model: str,
        source: str = "actual",
        timestamp: str | None = None,
    ) -> None:
        """Record the actual LLM route used for an agent.

        Args:
            agent_id: The agent identifier.
            transport: The transport type actually used.
            provider: The provider type actually used.
            model: The model actually used.
            source: Where the route came from (actual, fallback).
            timestamp: Optional timestamp for the route usage.
        """
        self.llm_actual_routes[agent_id] = LLMRouteRecord(
            agent_id=agent_id,
            transport=transport,
            provider=provider,
            model=model,
            source=source,
            timestamp=timestamp,
        )

    def record_llm_route_usage(
        self,
        agent_id: str,
        transport: str,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        error: bool = False,
    ) -> None:
        """Record usage statistics for an LLM route.

        Args:
            agent_id: The agent identifier.
            transport: The transport type used.
            prompt_tokens: Number of prompt tokens.
            completion_tokens: Number of completion tokens.
            latency_ms: Request latency in milliseconds.
            error: Whether the request resulted in an error.
        """
        key = f"{agent_id}:{transport}"
        if key not in self.llm_route_usage:
            self.llm_route_usage[key] = LLMRouteUsageStats()

        stats = self.llm_route_usage[key]
        stats.request_count += 1
        stats.prompt_tokens += prompt_tokens
        stats.completion_tokens += completion_tokens
        stats.total_tokens += prompt_tokens + completion_tokens
        stats.total_latency_ms += latency_ms
        if error:
            stats.error_count += 1

    def record_llm_route_fallback(
        self,
        agent_id: str,
        original_transport: str,
        fallback_transport: str,
        reason: str,
        timestamp: str | None = None,
    ) -> None:
        """Record an LLM route fallback event.

        Args:
            agent_id: The agent identifier.
            original_transport: The transport that failed or was unavailable.
            fallback_transport: The fallback transport being used.
            reason: Reason for the fallback.
            timestamp: Optional timestamp for the fallback event.
        """
        self.llm_fallback_events.append(
            {
                "agent_id": agent_id,
                "original_transport": original_transport,
                "fallback_transport": fallback_transport,
                "reason": reason,
                "timestamp": timestamp,
            }
        )
        self.note_execution_degradation(f"LLM fallback: {original_transport} -> {fallback_transport}")

    def get_llm_route_summary(self) -> dict[str, Any]:
        """Get a summary of LLM route usage for this session.

        Returns:
            Dictionary with planned routes, actual routes, usage stats, and fallbacks.
        """
        return {
            "planned_routes": {
                agent_id: {
                    "transport": route.transport,
                    "provider": route.provider,
                    "model": route.model,
                    "source": route.source,
                }
                for agent_id, route in self.llm_planned_routes.items()
            },
            "actual_routes": {
                agent_id: {
                    "transport": route.transport,
                    "provider": route.provider,
                    "model": route.model,
                    "source": route.source,
                }
                for agent_id, route in self.llm_actual_routes.items()
            },
            "usage_stats": {
                key: {
                    "request_count": stats.request_count,
                    "total_tokens": stats.total_tokens,
                    "prompt_tokens": stats.prompt_tokens,
                    "completion_tokens": stats.completion_tokens,
                    "error_count": stats.error_count,
                    "avg_latency_ms": (
                        stats.total_latency_ms // stats.request_count if stats.request_count > 0 else 0
                    ),
                }
                for key, stats in self.llm_route_usage.items()
            },
            "fallback_events": list(self.llm_fallback_events),
            "fallback_count": len(self.llm_fallback_events),
        }

    def build_metadata(
        self,
        *,
        depth: ResearchDepth,
        sources: list[SearchResultItem],
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

        analysis_payload = analysis.model_dump(mode="python")
        analysis_payload["source_provenance"] = _summarize_source_provenance(sources)

        return {
            "strategy": strategy.model_dump(mode="python"),
            "analysis": analysis_payload,
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
            "llm_routes": self.get_llm_route_summary(),
        }


def _summarize_source_provenance(sources: list[SearchResultItem]) -> dict[str, Any]:
    """Build a compact provenance summary for persisted session metadata."""
    queries: list[str] = []
    families: list[str] = []
    family_counts: dict[str, int] = {}
    sources_with_provenance = 0
    multi_query_sources = 0

    for source in sources:
        if not source.query_provenance:
            continue
        sources_with_provenance += 1
        if len(source.query_provenance) > 1:
            multi_query_sources += 1
        for entry in source.query_provenance:
            queries.append(entry.query)
            families.append(entry.family)
            family_counts[entry.family] = family_counts.get(entry.family, 0) + 1

    return {
        "sources_with_provenance": sources_with_provenance,
        "multi_query_sources": multi_query_sources,
        "queries": list(dict.fromkeys(queries)),
        "families": list(dict.fromkeys(families)),
        "family_counts": family_counts,
    }
