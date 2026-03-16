"""Sequential source collection strategy."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from cc_deep_research.config import Config
from cc_deep_research.models.search import (
    QueryFamily,
    ResearchDepth,
    SearchOptions,
    SearchResultItem,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.session_state import OrchestratorSessionState


class _SequentialCollector(Protocol):
    async def initialize_providers(self) -> None: ...
    def get_provider_warnings(self) -> list[str]: ...
    def get_available_providers(self) -> list[str]: ...
    async def collect_sources(
        self,
        query: str,
        options: SearchOptions,
        *,
        query_family: QueryFamily,
    ) -> list[SearchResultItem]: ...
    async def collect_multiple_queries(
        self,
        queries: list[str],
        options: SearchOptions,
        *,
        query_families: list[QueryFamily],
    ) -> list[SearchResultItem]: ...


class SequentialSourceCollectionStrategy:
    """Collect sources through configured providers without parallel fan-out."""

    def __init__(
        self,
        *,
        config: Config,
        monitor: ResearchMonitor,
        session_state: OrchestratorSessionState,
        hydrate_sources: Callable[[list[SearchResultItem], ResearchDepth], Awaitable[list[SearchResultItem]]],
        apply_source_limit: Callable[..., tuple[list[SearchResultItem], bool]],
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._session_state = session_state
        self._hydrate_sources = hydrate_sources
        self._apply_source_limit = apply_source_limit

    async def collect(
        self,
        *,
        collector: _SequentialCollector,
        query_families: list[QueryFamily],
        depth: ResearchDepth,
    ) -> list[SearchResultItem]:
        """Collect, hydrate, and limit sources sequentially."""
        self._monitor.section("Source Collection")
        queries = [family.query for family in query_families]

        await collector.initialize_providers()
        provider_warnings = collector.get_provider_warnings()
        self._session_state.set_provider_metadata(
            available=collector.get_available_providers(),
            warnings=provider_warnings,
        )
        for warning in provider_warnings:
            self._monitor.log(f"Provider warning: {warning}")

        max_results = self._config.research.min_sources.__dict__[depth.value]
        options = SearchOptions(
            max_results=max_results,
            search_depth=depth,
            monitor=self._monitor.is_enabled(),
            include_raw_content=True,
        )

        if len(queries) == 1:
            sources = await collector.collect_sources(
                queries[0],
                options,
                query_family=query_families[0],
            )
        else:
            sources = await collector.collect_multiple_queries(
                queries,
                options,
                query_families=query_families,
            )

        self._monitor.log(f"Collected {len(sources)} sources")
        self._monitor.record_reasoning_summary(
            stage="source_collection",
            summary=f"Collected {len(sources)} unique sources",
            agent_id="collector",
            query_count=len(queries),
        )
        self._monitor.record_source_provenance(
            query_families=query_families,
            sources=sources,
            stage="initial_collection",
        )

        hydrated_sources = await self._hydrate_sources(sources, depth)
        sources_with_content = sum(
            1 for source in hydrated_sources if source.content and len(source.content) > 500
        )
        self._monitor.log(
            f"Sources with full content: {sources_with_content}/{len(hydrated_sources)}"
        )

        depth_limits = {
            ResearchDepth.QUICK: 5,
            ResearchDepth.STANDARD: 15,
            ResearchDepth.DEEP: 50,
        }
        limit = depth_limits.get(depth, 10)
        limited_sources, _was_limited = self._apply_source_limit(
            sources=hydrated_sources,
            limit=limit,
            query=queries[0] if queries else "research",
        )
        return limited_sources


__all__ = ["SequentialSourceCollectionStrategy"]
