"""Source collection services used by the orchestrator."""

from __future__ import annotations

import asyncio
import time

from cc_deep_research.agents import ResearcherAgent, SourceCollectorAgent
from cc_deep_research.aggregation import ResultAggregator
from cc_deep_research.config import Config
from cc_deep_research.key_rotation import KeyRotationManager
from cc_deep_research.models import ResearchDepth, SearchOptions, SearchResult, SearchResultItem
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.helpers import decompose_parallel_tasks
from cc_deep_research.orchestration.session_state import OrchestratorSessionState
from cc_deep_research.providers.tavily import TavilySearchProvider


class SourceCollectionService:
    """Encapsulate sequential and parallel source collection workflows."""

    def __init__(
        self,
        *,
        config: Config,
        monitor: ResearchMonitor,
        session_state: OrchestratorSessionState,
        num_researchers: int,
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._session_state = session_state
        self._num_researchers = num_researchers
        self._content_cache: dict[str, str] = {}

    async def collect_sources(
        self,
        *,
        collector: SourceCollectorAgent,
        queries: list[str],
        depth: ResearchDepth,
    ) -> list[SearchResultItem]:
        """Collect sources through the configured provider set."""
        self._monitor.section("Source Collection")

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
            sources = await collector.collect_sources(queries[0], options)
        else:
            sources = await collector.collect_multiple_queries(queries, options)

        self._monitor.log(f"Collected {len(sources)} sources")
        self._monitor.record_reasoning_summary(
            stage="source_collection",
            summary=f"Collected {len(sources)} unique sources",
            agent_id="collector",
            query_count=len(queries),
        )

        hydrated_sources = await self.fetch_content_for_top_sources(sources=sources, depth=depth)
        sources_with_content = sum(
            1 for source in hydrated_sources if source.content and len(source.content) > 500
        )
        self._monitor.log(
            f"Sources with full content: {sources_with_content}/{len(hydrated_sources)}"
        )
        return hydrated_sources

    async def parallel_research(
        self,
        *,
        agent_pool: object | None,
        queries: list[str],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Collect sources using parallel researcher tasks."""
        self._monitor.section("Parallel Source Collection")

        if agent_pool is None:
            msg = "Agent pool not initialized for parallel mode"
            raise RuntimeError(msg)

        max_results_per_researcher = (
            min_sources or self._config.research.min_sources.__dict__[depth.value]
        ) // self._num_researchers

        provider_warnings: list[str] = []
        if not self._config.tavily.api_keys:
            provider_warnings.append(
                "Parallel source collection requires Tavily API keys, but none are configured."
            )
        if self._config.search.providers != ["tavily"]:
            provider_warnings.append(
                "Parallel source collection currently uses Tavily only, regardless of other configured providers."
            )
        self._session_state.set_provider_metadata(
            available=["tavily"] if self._config.tavily.api_keys else [],
            warnings=provider_warnings,
        )

        key_manager = KeyRotationManager(self._config.tavily.api_keys)
        provider = TavilySearchProvider(
            api_key=key_manager.get_available_key(),
            max_results=max_results_per_researcher,
        )
        researcher = ResearcherAgent(self._config, provider, monitor=self._monitor)
        tasks = decompose_parallel_tasks(queries)

        self._monitor.log(f"Decomposed {len(queries)} queries into {len(tasks)} tasks")
        for task in tasks:
            self._monitor.log_researcher_event(
                event_type="spawned",
                agent_id=task["task_id"],
                query=task["query"],
            )

        researcher_timeout = getattr(self._config.search_team, "researcher_timeout", 120)
        results = await researcher.execute_multiple_tasks(tasks, timeout=researcher_timeout)

        all_sources: list[SearchResultItem] = []
        for result in results:
            if result["status"] == "success":
                all_sources.extend(result["sources"])
                self._monitor.log(
                    f"✓ Researcher {result['task_id']}: "
                    f"{result['source_count']} sources "
                    f"({result['execution_time_ms']:.0f}ms)"
                )
                self._monitor.log_researcher_event(
                    event_type="completed",
                    agent_id=result["task_id"],
                    source_count=result["source_count"],
                    duration_ms=int(result["execution_time_ms"]),
                    status="completed",
                )
                self._monitor.record_reasoning_summary(
                    stage="researcher_task",
                    summary=f"Executed query and gathered {result['source_count']} sources",
                    agent_id=result["task_id"],
                    query=result.get("query", ""),
                )
                continue

            self._monitor.log(
                f"✗ Researcher {result['task_id']}: "
                f"{result['status']} - {result.get('error', 'Unknown error')}"
            )
            self._monitor.log_researcher_event(
                event_type="failed" if result["status"] != "timeout" else "timeout",
                agent_id=result["task_id"],
                status=result["status"],
                error=result.get("error", "Unknown error"),
            )

        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=self._monitor.is_enabled(),
        )
        for source in all_sources:
            aggregator.add_result(
                SearchResult(
                    query="parallel-research",
                    results=[source],
                    provider="tavily",
                )
            )

        aggregated = aggregator.get_aggregated()
        self._session_state.mark_parallel_collection_used()
        self._monitor.log(f"Collected {len(aggregated)} unique sources (parallel)")
        return await self.fetch_content_for_top_sources(sources=aggregated, depth=depth)

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

        try:
            from mcp__web_reader__webReader import webReader  # type: ignore[import-not-found]

            start_time = time.time()
            result = webReader(
                url=url,
                timeout=15,
                return_format="markdown",
                retain_images=False,
            )

            if isinstance(result, dict) and "content" in result:
                content = str(result["content"])
                self._content_cache[url] = content
                self._monitor.record_tool_call(
                    tool_name="mcp.web_reader",
                    status="success",
                    duration_ms=int((time.time() - start_time) * 1000),
                    url=url,
                )
                return content

            if isinstance(result, str):
                self._content_cache[url] = result
                self._monitor.record_tool_call(
                    tool_name="mcp.web_reader",
                    status="success",
                    duration_ms=int((time.time() - start_time) * 1000),
                    url=url,
                )
                return result

            self._monitor.record_tool_call(
                tool_name="mcp.web_reader",
                status="error",
                duration_ms=int((time.time() - start_time) * 1000),
                url=url,
                error="No content returned",
            )
            return None
        except ImportError:
            self._monitor.log("web_reader MCP not available, skipping content fetch")
            return None
        except Exception as exc:
            self._monitor.log(f"Error fetching page content: {exc}")
            self._monitor.record_tool_call(
                tool_name="mcp.web_reader",
                status="error",
                duration_ms=0,
                url=url,
                error=str(exc),
            )
            return None
