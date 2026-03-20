"""Source collector agent implementation.

The source collector agent is responsible for:
- Gathering sources from configured search providers (Tavily, Claude WebSearch)
- Managing API key rotation
- Handling rate limits and errors
- Collecting source metadata
"""

import asyncio
import time

from cc_deep_research.aggregation import ResultAggregator
from cc_deep_research.config import Config
from cc_deep_research.models import QueryFamily, SearchOptions, SearchResult, SearchResultItem
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.providers import SearchProvider, resolve_provider_specs
from cc_deep_research.providers.factory import build_search_providers


class SourceCollectorAgent:
    """Agent that collects sources from configured providers.

    This agent handles:
    - Querying multiple search providers
    - Managing API rate limits and key rotation
    - Aggregating results from multiple sources
    - Error handling and retries
    """

    def __init__(
        self,
        config: Config,
        monitor: ResearchMonitor | None = None,
    ) -> None:
        """Initialize the source collector agent.

        Args:
            config: Application configuration.
            monitor: Optional monitor for telemetry capture.
        """
        self._config = config
        self._monitor = monitor
        self._providers: list[SearchProvider] = []
        self._provider_warnings: list[str] = []

    async def initialize_providers(self) -> None:
        """Initialize search providers from configuration.

        This method creates provider instances based on the
        configured search providers and API keys.
        """
        self._providers, self._provider_warnings = build_search_providers(
            self._config,
            resolve_provider_specs(self._config),
        )

    async def collect_sources(
        self,
        query: str,
        options: SearchOptions | None = None,
        query_family: QueryFamily | None = None,
    ) -> list[SearchResultItem]:
        """Collect sources for a given query.

        Args:
            query: Search query string.
            options: Search options (max_results, depth, etc.).

        Returns:
            List of search result items from all providers. Returns an empty
            list when no configured provider can be used or all searches fail.
        """
        if not self._providers:
            await self.initialize_providers()

        if not self._providers:
            return []

        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=options.monitor if options else False,
        )

        # Execute searches in parallel
        effective_family = query_family or QueryFamily(query=query)
        tasks = [
            self._search_provider(
                provider,
                query,
                options,
                query_family=effective_family,
            )
            for provider in self._providers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful_results = 0
        for result in results:
            if isinstance(result, Exception):
                # Log error but continue with other providers
                continue
            successful_results += 1
            aggregator.add_result(result)  # type: ignore[arg-type]

        if successful_results == 0:
            self._provider_warnings.append(self._build_all_failed_message(query))

        return aggregator.get_aggregated()

    async def collect_multiple_queries(
        self,
        queries: list[str],
        options: SearchOptions | None = None,
        query_families: list[QueryFamily] | None = None,
    ) -> list[SearchResultItem]:
        """Collect sources for multiple queries.

        Args:
            queries: List of search query strings.
            options: Search options.

        Returns:
            Aggregated list of search result items. Returns an empty list when
            no configured provider can be used or all searches fail.
        """
        if not self._providers:
            await self.initialize_providers()

        if not self._providers:
            return []

        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=options.monitor if options else False,
        )

        # Execute all queries in parallel
        all_tasks = []
        for family in self._resolve_query_families(queries, query_families):
            for provider in self._providers:
                all_tasks.append(
                    self._search_provider(
                        provider,
                        family.query,
                        options,
                        query_family=family,
                    )
                )

        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Process results
        successful_results = 0
        for result in results:
            if not isinstance(result, Exception):
                successful_results += 1
                aggregator.add_result(result)  # type: ignore[arg-type]

        if successful_results == 0:
            self._provider_warnings.append(self._build_all_failed_message(", ".join(queries)))

        return aggregator.get_aggregated()

    def get_available_providers(self) -> list[str]:
        """Get list of available search providers.

        Returns:
            List of provider names.
        """
        return [p.get_provider_name() for p in self._providers]

    def get_provider_warnings(self) -> list[str]:
        """Return warnings collected while resolving providers."""
        return list(self._provider_warnings)

    async def close_providers(self) -> None:
        """Close all initialized providers."""
        await asyncio.gather(
            *(provider.close() for provider in self._providers),
            return_exceptions=True,
        )

    async def _search_provider(
        self,
        provider: SearchProvider,
        query: str,
        options: SearchOptions | None,
        *,
        query_family: QueryFamily,
    ) -> object:
        """Execute one provider search and emit telemetry for visibility."""
        start_time = time.time()
        provider_name = provider.get_provider_name()
        if self._monitor:
            self._monitor.record_tool_call(
                tool_name=f"{provider_name}.search",
                status="started",
                duration_ms=0,
                query=query,
            )

        try:
            result = await provider.search(query, options)
            result = self._attach_query_provenance(result, query_family)
            duration_ms = int((time.time() - start_time) * 1000)
            if self._monitor:
                self._monitor.record_search_query(
                    query=query,
                    provider=provider_name,
                    result_count=len(result.results),
                    duration_ms=duration_ms,
                    status="success",
                )
                self._monitor.record_tool_call(
                    tool_name=f"{provider_name}.search",
                    status="success",
                    duration_ms=duration_ms,
                    query=query,
                    result_count=len(result.results),
                )
            return result
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._monitor:
                self._monitor.record_search_query(
                    query=query,
                    provider=provider_name,
                    result_count=0,
                    duration_ms=duration_ms,
                    status="error",
                    error=str(exc),
                )
                self._monitor.record_tool_call(
                    tool_name=f"{provider_name}.search",
                    status="error",
                    duration_ms=duration_ms,
                    query=query,
                    error=str(exc),
                )
            return exc

    def _attach_query_provenance(
        self,
        result: SearchResult,
        query_family: QueryFamily,
    ) -> SearchResult:
        """Attach query provenance to all items returned for one query variation."""
        annotated_results: list[SearchResultItem] = []
        for item in result.results:
            annotated = item.model_copy(deep=True)
            annotated.add_query_provenance(
                query=query_family.query,
                family=query_family.family,
                intent_tags=list(query_family.intent_tags),
            )
            annotated_results.append(annotated)
        return result.model_copy(update={"results": annotated_results}, deep=True)

    def _resolve_query_families(
        self,
        queries: list[str],
        query_families: list[QueryFamily] | None,
    ) -> list[QueryFamily]:
        """Return one query-family record for each query in collection order."""
        if not query_families:
            return [QueryFamily(query=query) for query in queries]

        families_by_query = {family.query: family for family in query_families}
        return [families_by_query.get(query, QueryFamily(query=query)) for query in queries]

    def _build_unavailable_message(self) -> str:
        """Build a useful error message for unavailable providers."""
        if self._provider_warnings:
            warning_text = " ".join(self._provider_warnings)
            return f"No search providers available. {warning_text}"
        return "No search providers available. Please configure at least one supported provider."

    def _build_all_failed_message(self, query: str) -> str:
        """Build a warning when all initialized providers fail a search."""
        provider_names = ", ".join(self.get_available_providers()) or "configured providers"
        return (
            f"All initialized providers failed for query '{query}'. "
            f"Continuing with an empty result set from: {provider_names}."
        )


class SourceCollectionError(Exception):
    """Exception raised when source collection fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.query = query
        self.original_error = original_error


__all__ = ["SourceCollectorAgent", "SourceCollectionError"]
