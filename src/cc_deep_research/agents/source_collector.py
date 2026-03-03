"""Source collector agent implementation.

The source collector agent is responsible for:
- Gathering sources from configured search providers (Tavily, Claude WebSearch)
- Managing API key rotation
- Handling rate limits and errors
- Collecting source metadata
"""

import asyncio
from typing import Any

from cc_deep_research.aggregation import ResultAggregator
from cc_deep_research.config import Config
from cc_deep_research.models import SearchOptions, SearchResultItem
from cc_deep_research.providers import SearchProvider
from cc_deep_research.providers.tavily import TavilySearchProvider


class SourceCollectorAgent:
    """Agent that collects sources from configured providers.

    This agent handles:
    - Querying multiple search providers
    - Managing API rate limits and key rotation
    - Aggregating results from multiple sources
    - Error handling and retries
    """

    def __init__(self, config: Config) -> None:
        """Initialize the source collector agent.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._providers: list[SearchProvider] = []

    async def initialize_providers(self) -> None:
        """Initialize search providers from configuration.

        This method creates provider instances based on the
        configured search providers and API keys.
        """
        self._providers = []

        # Initialize Tavily provider if keys are configured
        if self._config.tavily.api_keys:
            from cc_deep_research.key_rotation import KeyRotationManager

            key_manager = KeyRotationManager(self._config.tavily.api_keys)
            provider = TavilySearchProvider(
                api_key=key_manager.get_available_key(),
                max_results=self._config.tavily.max_results,
            )
            self._providers.append(provider)

        # Initialize Claude WebSearch provider (placeholder)
        # Would need to implement Claude WebSearch provider
        # if "claude" in self._config.search.providers

    async def collect_sources(
        self,
        query: str,
        options: SearchOptions | None = None,
    ) -> list[SearchResultItem]:
        """Collect sources for a given query.

        Args:
            query: Search query string.
            options: Search options (max_results, depth, etc.).

        Returns:
            List of search result items from all providers.

        Raises:
            SourceCollectionError: If collection fails completely.
        """
        if not self._providers:
            await self.initialize_providers()

        if not self._providers:
            raise SourceCollectionError(
                "No search providers available. Please configure API keys."
            )

        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=options.monitor if options else False,
        )

        # Execute searches in parallel
        tasks = [
            provider.search(query, options) for provider in self._providers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                # Log error but continue with other providers
                continue
            aggregator.add_result(result)

        return aggregator.get_aggregated()

    async def collect_multiple_queries(
        self,
        queries: list[str],
        options: SearchOptions | None = None,
    ) -> list[SearchResultItem]:
        """Collect sources for multiple queries.

        Args:
            queries: List of search query strings.
            options: Search options.

        Returns:
            Aggregated list of search result items.
        """
        if not self._providers:
            await self.initialize_providers()

        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=options.monitor if options else False,
        )

        # Execute all queries in parallel
        all_tasks = []
        for query in queries:
            for provider in self._providers:
                all_tasks.append(provider.search(query, options))

        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Process results
        for result in results:
            if not isinstance(result, Exception):
                aggregator.add_result(result)

        return aggregator.get_aggregated()

    def get_available_providers(self) -> list[str]:
        """Get list of available search providers.

        Returns:
            List of provider names.
        """
        return [p.get_provider_name() for p in self._providers]


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
