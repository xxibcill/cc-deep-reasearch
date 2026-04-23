"""Source collection facade and shared helpers for orchestrator workflows."""

from __future__ import annotations

import asyncio
import time

from cc_deep_research.aggregation import ResultAggregator
from cc_deep_research.config import Config
from cc_deep_research.models.search import (
    QueryFamily,
    ResearchDepth,
    SearchResult,
    SearchResultItem,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.session_state import OrchestratorSessionState

from .resilience import (
    build_parallel_collection_policy,
)
from .source_collection_parallel import ParallelSourceCollectionStrategy, _emit_agent_lifecycle
from .source_collection_sequential import SequentialSourceCollectionStrategy, _SequentialCollector


class SourceAggregationService:
    """Share source aggregation rules across collection strategies."""

    def __init__(self, *, monitor: ResearchMonitor) -> None:
        self._monitor = monitor

    def aggregate_parallel_sources(self, sources: list[SearchResultItem]) -> list[SearchResultItem]:
        """Deduplicate and rank sources collected by parallel researchers."""
        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=self._monitor.is_enabled(),
        )
        for source in sources:
            aggregator.add_result(
                SearchResult(
                    query="parallel-research",
                    results=[source],
                    provider="tavily",
                )
            )
        return aggregator.get_aggregated()

    def apply_source_limit(
        self,
        *,
        sources: list[SearchResultItem],
        limit: int,
        query: str,
    ) -> tuple[list[SearchResultItem], bool]:
        """Apply source limit and signal if more sources may still be needed."""
        if len(sources) <= limit:
            return sources[:limit], False

        sorted_sources = sorted(
            sources,
            key=lambda source: getattr(source, "relevance_score", 0)
            or getattr(source, "score", 0),
            reverse=True,
        )
        limited_sources = sorted_sources[:limit]
        self._monitor.log(
            f"Source limit applied: kept {len(limited_sources)}/{len(sources)} for query '{query}' (limit={limit})"
        )
        return limited_sources, True

    def merge_sources(
        self,
        *,
        existing_sources: list[SearchResultItem],
        new_sources: list[SearchResultItem],
    ) -> list[SearchResultItem]:
        """Merge and deduplicate sources while preserving ranking."""
        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=self._monitor.is_enabled(),
        )
        for source_set, provider in (
            (existing_sources, "existing"),
            (new_sources, "follow-up"),
        ):
            for source in source_set:
                aggregator.add_result(
                    SearchResult(
                        query="iterative-search",
                        results=[source],
                        provider=provider,
                    )
                )
        return aggregator.get_aggregated()


class SourceContentHydrator:
    """Populate top-ranked sources with fetched page content when available."""

    def __init__(
        self,
        *,
        config: Config,
        monitor: ResearchMonitor,
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._content_cache: dict[str, str] = {}
        self._timeouts = build_parallel_collection_policy(config).timeouts

    async def fetch_content_for_top_sources(
        self,
        *,
        sources: list[SearchResultItem],
        depth: ResearchDepth,
    ) -> list[SearchResultItem]:
        """Fetch full content for top-ranked sources when available."""
        num_to_fetch = getattr(self._config.research, "top_sources_for_content", 15)
        if depth != ResearchDepth.DEEP:
            num_to_fetch = min(num_to_fetch, 10)

        sorted_sources = sorted(sources, key=lambda source: source.score or 0, reverse=True)
        top_sources = sorted_sources[:num_to_fetch]
        if not top_sources:
            return sources

        self._monitor.log(f"Fetching full content for top {len(top_sources)} sources...")
        sources_needing_fetch = [
            source
            for source in sources
            if source in top_sources and not (source.content and len(source.content) > 500)
        ]
        await asyncio.gather(
            *(self.populate_source_content(source) for source in sources_needing_fetch),
            return_exceptions=True,
        )
        return sources

    async def populate_source_content(self, source: SearchResultItem) -> None:
        """Populate a source with fetched page content when available."""
        try:
            content = await self.fetch_page_content(source.url)
            if content and len(content) > 200:
                source.content = content
                title = source.title[:50] if source.title else source.url
                self._monitor.log(f"  ✓ Fetched content for: {title}...")
        except Exception as exc:
            self._monitor.log(f"  ✗ Failed to fetch {source.url}: {exc}")

    async def fetch_page_content(self, url: str) -> str | None:
        """Fetch page content using the optional web-reader MCP tool."""
        cached_content = self._content_cache.get(url)
        if cached_content is not None:
            return cached_content

        current_parent = self._monitor.current_parent_id
        tool_event_id = self._monitor.emit_event(
            event_type="tool.started",
            category="tool",
            name="mcp.web_reader",
            status="started",
            parent_event_id=current_parent,
            metadata={
                "url": url,
                "timeout_seconds": self._timeouts.content_fetch_timeout_seconds,
            },
        )

        try:
            from mcp__web_reader__webReader import webReader  # type: ignore[import-not-found]

            start_time = time.time()
            timeout_seconds = self._timeouts.content_fetch_timeout_seconds
            result = webReader(
                url=url,
                timeout=timeout_seconds,
                return_format="markdown",
                retain_images=False,
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if isinstance(result, dict) and "content" in result:
                content = str(result["content"])
                self._content_cache[url] = content
                self._monitor.emit_event(
                    event_type="tool.completed",
                    category="tool",
                    name="mcp.web_reader",
                    status="completed",
                    duration_ms=duration_ms,
                    parent_event_id=tool_event_id,
                    metadata={
                        "url": url,
                        "content_length": len(content),
                        "timeout_seconds": timeout_seconds,
                    },
                )
                self._monitor.record_tool_call(
                    tool_name="mcp.web_reader",
                    status="success",
                    duration_ms=duration_ms,
                    url=url,
                    timeout_seconds=timeout_seconds,
                )
                return content

            if isinstance(result, str):
                self._content_cache[url] = result
                self._monitor.emit_event(
                    event_type="tool.completed",
                    category="tool",
                    name="mcp.web_reader",
                    status="completed",
                    duration_ms=duration_ms,
                    parent_event_id=tool_event_id,
                    metadata={
                        "url": url,
                        "content_length": len(result),
                        "timeout_seconds": timeout_seconds,
                    },
                )
                self._monitor.record_tool_call(
                    tool_name="mcp.web_reader",
                    status="success",
                    duration_ms=duration_ms,
                    url=url,
                    timeout_seconds=timeout_seconds,
                )
                return result

            self._monitor.emit_event(
                event_type="tool.failed",
                category="tool",
                name="mcp.web_reader",
                status="failed",
                duration_ms=duration_ms,
                parent_event_id=tool_event_id,
                metadata={
                    "url": url,
                    "error": "No content returned",
                    "timeout_seconds": timeout_seconds,
                },
            )
            self._monitor.record_tool_call(
                tool_name="mcp.web_reader",
                status="error",
                duration_ms=duration_ms,
                url=url,
                error="No content returned",
                timeout_seconds=timeout_seconds,
            )
            return None
        except ImportError:
            self._monitor.log("web_reader MCP not available, skipping content fetch")
            self._monitor.emit_event(
                event_type="tool.failed",
                category="tool",
                name="mcp.web_reader",
                status="unavailable",
                parent_event_id=tool_event_id,
                metadata={"url": url, "error": "web_reader MCP not available"},
            )
            return None
        except Exception as exc:
            self._monitor.log(f"Error fetching page content: {exc}")
            self._monitor.emit_event(
                event_type="tool.failed",
                category="tool",
                name="mcp.web_reader",
                status="failed",
                parent_event_id=tool_event_id,
                metadata={"url": url, "error": str(exc), "error_type": type(exc).__name__},
            )
            self._monitor.record_tool_call(
                tool_name="mcp.web_reader",
                status="error",
                duration_ms=0,
                url=url,
                error=str(exc),
            )
            return None


class SourceCollectionService:
    """Coordinate sequential and parallel source collection strategies."""

    def __init__(
        self,
        *,
        config: Config,
        monitor: ResearchMonitor,
        session_state: OrchestratorSessionState,
        max_concurrent_sources: int,
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._session_state = session_state
        self._aggregation = SourceAggregationService(monitor=monitor)
        self._hydrator = SourceContentHydrator(config=config, monitor=monitor)
        self._sequential = SequentialSourceCollectionStrategy(
            config=config,
            monitor=monitor,
            session_state=session_state,
            hydrate_sources=self._hydrate_sources,
            apply_source_limit=self._aggregation.apply_source_limit,
        )
        self._parallel = ParallelSourceCollectionStrategy(
            config=config,
            monitor=monitor,
            session_state=session_state,
            max_concurrent_sources=max_concurrent_sources,
            hydrate_sources=self._hydrate_sources,
            aggregate_sources=self._aggregation.aggregate_parallel_sources,
        )

    async def collect_with_fallback(
        self,
        *,
        collector: _SequentialCollector,
        agent_pool: object | None,
        query_families: list[QueryFamily],
        depth: ResearchDepth,
        min_sources: int | None,
        prefer_parallel: bool,
    ) -> list[SearchResultItem]:
        """Collect sources, falling back to sequential mode when parallel fails."""
        policy = build_parallel_collection_policy(self._config)
        if prefer_parallel and agent_pool:
            try:
                return await self.parallel_research(
                    agent_pool=agent_pool,
                    query_families=query_families,
                    depth=depth,
                    min_sources=min_sources,
                )
            except Exception as exc:
                if not policy.fallback_to_sequential:
                    raise
                self._monitor.log(f"Parallel execution failed: {exc}")
                self._monitor.log("Falling back to sequential mode")
                self._monitor.emit_decision_made(
                    decision_type="collection_fallback",
                    reason_code="fallback",
                    chosen_option="sequential",
                    inputs={
                        "requested_mode": "parallel",
                        "fallback_enabled": policy.fallback_to_sequential,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
                self._session_state.note_execution_degradation(
                    f"Parallel source collection fell back to sequential mode: {exc}"
                )

        return await self.collect_sources(
            collector=collector,
            query_families=query_families,
            depth=depth,
        )

    async def collect_follow_up_sources(
        self,
        *,
        collector: _SequentialCollector,
        agent_pool: object | None,
        follow_up_queries: list[str],
        depth: ResearchDepth,
        min_sources: int | None,
        prefer_parallel: bool,
    ) -> list[SearchResultItem]:
        """Collect follow-up sources using the same execution mode rules."""
        return await self.collect_with_fallback(
            collector=collector,
            agent_pool=agent_pool,
            query_families=[
                QueryFamily(
                    query=query,
                    family="follow-up",
                    intent_tags=["follow-up"],
                )
                for query in follow_up_queries
            ],
            depth=depth,
            min_sources=min_sources,
            prefer_parallel=prefer_parallel,
        )

    async def collect_sources(
        self,
        *,
        collector: _SequentialCollector,
        query_families: list[QueryFamily],
        depth: ResearchDepth,
    ) -> list[SearchResultItem]:
        """Run the sequential provider-backed collection strategy."""
        return await self._sequential.collect(
            collector=collector,
            query_families=query_families,
            depth=depth,
        )

    async def parallel_research(
        self,
        *,
        agent_pool: object | None,
        query_families: list[QueryFamily],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Run the parallel researcher-backed collection strategy."""
        return await self._parallel.collect(
            agent_pool=agent_pool,
            query_families=query_families,
            depth=depth,
            min_sources=min_sources,
        )

    def merge_sources(
        self,
        *,
        existing_sources: list[SearchResultItem],
        new_sources: list[SearchResultItem],
    ) -> list[SearchResultItem]:
        """Merge and deduplicate sources while preserving ranking."""
        return self._aggregation.merge_sources(
            existing_sources=existing_sources,
            new_sources=new_sources,
        )

    def apply_source_limit(
        self,
        *,
        sources: list[SearchResultItem],
        limit: int,
        query: str,
    ) -> tuple[list[SearchResultItem], bool]:
        """Expose the shared limit helper for compatibility."""
        return self._aggregation.apply_source_limit(sources=sources, limit=limit, query=query)

    async def fetch_content_for_top_sources(
        self,
        *,
        sources: list[SearchResultItem],
        depth: ResearchDepth,
    ) -> list[SearchResultItem]:
        """Expose the hydrator for compatibility."""
        return await self._hydrator.fetch_content_for_top_sources(sources=sources, depth=depth)

    async def populate_source_content(self, source: SearchResultItem) -> None:
        """Expose the hydrator for compatibility."""
        await self._hydrator.populate_source_content(source)

    async def fetch_page_content(self, url: str) -> str | None:
        """Expose the hydrator for compatibility."""
        return await self._hydrator.fetch_page_content(url)

    async def _hydrate_sources(
        self,
        sources: list[SearchResultItem],
        depth: ResearchDepth,
    ) -> list[SearchResultItem]:
        """Adapt the shared hydrator to the strategy callback signature."""
        return await self._hydrator.fetch_content_for_top_sources(sources=sources, depth=depth)


__all__ = [
    "SourceAggregationService",
    "SourceCollectionService",
    "SourceContentHydrator",
    "_emit_agent_lifecycle",
]
