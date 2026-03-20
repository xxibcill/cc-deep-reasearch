"""Parallel source collection strategy."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from cc_deep_research.agents import ResearcherAgent
from cc_deep_research.config import Config
from cc_deep_research.models.search import QueryFamily, ResearchDepth, SearchResultItem
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.helpers import decompose_parallel_tasks
from cc_deep_research.orchestration.session_state import OrchestratorSessionState
from cc_deep_research.providers import ProviderSpec
from cc_deep_research.providers.factory import build_search_provider


def _emit_agent_lifecycle(
    monitor: ResearchMonitor,
    *,
    event_type: str,
    agent_id: str,
    agent_type: str,
    status: str,
    parent_event_id: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Emit a standardized agent lifecycle event."""
    return monitor.emit_event(
        event_type=event_type,
        category="agent",
        name=agent_type,
        agent_id=agent_id,
        status=status,
        parent_event_id=parent_event_id,
        metadata={"agent_type": agent_type, **(metadata or {})},
    )


class ParallelSourceCollectionStrategy:
    """Collect sources using parallel local researcher tasks."""

    def __init__(
        self,
        *,
        config: Config,
        monitor: ResearchMonitor,
        session_state: OrchestratorSessionState,
        num_researchers: int,
        hydrate_sources: Callable[[list[SearchResultItem], ResearchDepth], Awaitable[list[SearchResultItem]]],
        aggregate_sources: Callable[[list[SearchResultItem]], list[SearchResultItem]],
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._session_state = session_state
        self._num_researchers = num_researchers
        self._hydrate_sources = hydrate_sources
        self._aggregate_sources = aggregate_sources

    async def collect(
        self,
        *,
        agent_pool: object | None,
        query_families: list[QueryFamily],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Collect, aggregate, and hydrate sources in parallel."""
        self._monitor.section("Parallel Source Collection")
        queries = [family.query for family in query_families]

        if agent_pool is None:
            raise RuntimeError("Local agent pool not initialized for parallel mode")

        max_results_per_researcher = (
            min_sources or self._config.research.min_sources.__dict__[depth.value]
        ) // self._num_researchers

        provider_warnings = self._build_provider_warnings()
        self._session_state.set_provider_metadata(
            available=["tavily"] if self._config.tavily.api_keys else [],
            warnings=provider_warnings,
        )

        provider = build_search_provider(
            self._config,
            ProviderSpec(
                configured_name="tavily",
                provider_type="tavily",
                provider_name="tavily",
            ),
            max_results_override=max_results_per_researcher,
        )
        if provider is None:
            return []

        researcher = ResearcherAgent(self._config, provider, monitor=self._monitor)
        tasks = decompose_parallel_tasks(queries)

        current_parent = self._monitor.current_parent_id
        self._monitor.log(f"Decomposed {len(queries)} queries into {len(tasks)} tasks")

        task_agent_ids: dict[str, str] = {}
        for task in tasks:
            agent_event_id = _emit_agent_lifecycle(
                self._monitor,
                event_type="agent.spawned",
                agent_id=task["task_id"],
                agent_type="researcher",
                status="spawned",
                parent_event_id=current_parent,
                metadata={"query": task["query"]},
            )
            task_agent_ids[task["task_id"]] = agent_event_id
            self._monitor.log_researcher_event(
                event_type="spawned",
                agent_id=task["task_id"],
                query=task["query"],
            )

        researcher_timeout = getattr(self._config.search_team, "researcher_timeout", 120)
        results = await researcher.execute_multiple_tasks(tasks, timeout=researcher_timeout)

        all_sources: list[SearchResultItem] = []
        families_by_query = {family.query: family for family in query_families}
        for result in results:
            task_id = result["task_id"]
            agent_event_id = task_agent_ids.get(task_id)

            if result["status"] == "success":
                family = families_by_query.get(
                    result.get("query", ""),
                    QueryFamily(
                        query=result.get("query", "") or "parallel-research",
                        family="parallel",
                        intent_tags=["parallel"],
                    ),
                )
                for source in result["sources"]:
                    source.add_query_provenance(
                        query=family.query,
                        family=family.family,
                        intent_tags=list(family.intent_tags),
                    )
                all_sources.extend(result["sources"])
                self._monitor.log(
                    f"✓ Researcher {task_id}: "
                    f"{result['source_count']} sources "
                    f"({result['execution_time_ms']:.0f}ms)"
                )
                _emit_agent_lifecycle(
                    self._monitor,
                    event_type="agent.completed",
                    agent_id=task_id,
                    agent_type="researcher",
                    status="completed",
                    parent_event_id=agent_event_id,
                    metadata={
                        "source_count": result["source_count"],
                        "duration_ms": int(result["execution_time_ms"]),
                        "query": result.get("query", ""),
                    },
                )
                self._monitor.log_researcher_event(
                    event_type="completed",
                    agent_id=task_id,
                    source_count=result["source_count"],
                    duration_ms=int(result["execution_time_ms"]),
                    status="completed",
                )
                self._monitor.record_reasoning_summary(
                    stage="researcher_task",
                    summary=f"Executed query and gathered {result['source_count']} sources",
                    agent_id=task_id,
                    query=result.get("query", ""),
                )
                continue

            self._monitor.log(
                f"✗ Researcher {task_id}: "
                f"{result['status']} - {result.get('error', 'Unknown error')}"
            )
            _emit_agent_lifecycle(
                self._monitor,
                event_type="agent.failed" if result["status"] != "timeout" else "agent.timeout",
                agent_id=task_id,
                agent_type="researcher",
                status=result["status"],
                parent_event_id=agent_event_id,
                metadata={
                    "error": result.get("error", "Unknown error"),
                    "query": result.get("query", ""),
                },
            )
            self._monitor.log_researcher_event(
                event_type="failed" if result["status"] != "timeout" else "timeout",
                agent_id=task_id,
                status=result["status"],
                error=result.get("error", "Unknown error"),
            )

        aggregated = self._aggregate_sources(all_sources)
        self._session_state.mark_parallel_collection_used()
        self._monitor.log(f"Collected {len(aggregated)} unique sources (parallel)")
        self._monitor.record_source_provenance(
            query_families=query_families,
            sources=aggregated,
            stage="parallel_collection",
        )
        return await self._hydrate_sources(aggregated, depth)

    def _build_provider_warnings(self) -> list[str]:
        """Return provider warnings for the parallel Tavily-only path."""
        warnings: list[str] = []
        if not self._config.tavily.api_keys:
            warnings.append(
                "Parallel source collection requires Tavily API keys, but none are configured."
            )
        if self._config.search.providers != ["tavily"]:
            warnings.append(
                "Parallel source collection currently uses Tavily only, regardless of other configured providers."
            )
        return warnings


__all__ = ["ParallelSourceCollectionStrategy"]
