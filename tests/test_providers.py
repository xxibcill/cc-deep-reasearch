"""Tests and fixtures for search provider integrations."""

import asyncio
from typing import Any

import pytest

from cc_deep_research.agents.source_collector import SourceCollectorAgent
from cc_deep_research.aggregation import ResultAggregator, deduplicate_by_url
from cc_deep_research.config import Config
from cc_deep_research.models import SearchMode, SearchOptions, SearchResult, SearchResultItem
from cc_deep_research.models.search import QueryFamily, ResearchDepth
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.resilience import ParallelCollectionTimeoutError
from cc_deep_research.orchestration.session_state import OrchestratorSessionState
from cc_deep_research.orchestration.source_collection import (
    SourceAggregationService,
    SourceCollectionService,
)
from cc_deep_research.orchestration.source_collection_parallel import (
    ParallelSourceCollectionStrategy,
)
from cc_deep_research.providers import (
    AuthenticationError,
    NetworkError,
    ProviderSpec,
    RateLimitError,
    SearchProvider,
    SearchProviderError,
    resolve_provider_specs,
)
from cc_deep_research.providers.cached import CachedSearchProvider
from cc_deep_research.search_cache import InFlightSearchRegistry, SearchCacheStore


class MockSearchProvider(SearchProvider):
    """Mock implementation of SearchProvider for testing."""

    def __init__(
        self,
        name: str = "mock",
        should_fail: bool = False,
        fail_with: Exception | None = None,
    ) -> None:
        self._name = name
        self._should_fail = should_fail
        self._fail_with = fail_with
        self._is_available = True
        self.search_calls: list[tuple[str, SearchOptions | None]] = []

    async def search(self, query: str, options: SearchOptions | None = None) -> SearchResult:
        """Mock search implementation."""
        self.search_calls.append((query, options))

        if self._should_fail:
            if self._fail_with:
                raise self._fail_with
            raise SearchProviderError("Mock failure", self._name, query)

        max_results = options.max_results if options else 10
        items = [
            SearchResultItem(
                url=f"https://example.com/result/{i}",
                title=f"Result {i} for: {query}",
                snippet=f"Snippet {i}",
                score=max(0.0, 0.9 - (i * 0.1)),
            )
            for i in range(1, max_results + 1)
        ]

        return SearchResult(
            query=query,
            results=items,
            provider=self._name,
            execution_time_ms=100,
        )

    def get_provider_name(self) -> str:
        """Return mock provider name."""
        return self._name

    @property
    def is_available(self) -> bool:
        """Return mock availability."""
        return self._is_available

    def set_available(self, available: bool) -> None:
        """Set availability for testing."""
        self._is_available = available


def build_search_result_item(
    suffix: str,
    *,
    title: str | None = None,
    snippet: str | None = None,
    score: float = 0.9,
    content: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> SearchResultItem:
    """Build a deterministic search result item for contract tests."""
    return SearchResultItem(
        url=f"https://example.com/{suffix}",
        title=title or f"Result for {suffix}",
        snippet=snippet or f"Snippet for {suffix}",
        score=score,
        content=content,
        source_metadata=source_metadata or {},
    )


class FixtureSearchProvider(SearchProvider):
    """Deterministic provider fixture for workflow contract tests."""

    def __init__(
        self,
        *,
        name: str = "fixture",
        results_by_query: dict[str, list[SearchResultItem]] | None = None,
        available: bool = True,
        fail_with: Exception | None = None,
    ) -> None:
        self._name = name
        self._results_by_query = results_by_query or {}
        self._is_available = available
        self._fail_with = fail_with
        self.search_calls: list[tuple[str, SearchOptions | None]] = []

    async def search(self, query: str, options: SearchOptions | None = None) -> SearchResult:
        """Return pre-seeded results or generate stable fallback items."""
        self.search_calls.append((query, options))

        if self._fail_with is not None:
            raise self._fail_with

        items = self._results_by_query.get(query)
        if items is None:
            max_results = options.max_results if options else 2
            slug = query.lower().replace(" ", "-")
            items = [
                build_search_result_item(
                    f"{slug}-{index}",
                    title=f"{query} result {index}",
                    score=max(0.1, 1.0 - (index * 0.1)),
                )
                for index in range(1, max_results + 1)
            ]

        return SearchResult(
            query=query,
            results=[item.model_copy(deep=True) for item in items],
            provider=self._name,
            execution_time_ms=25,
        )

    def get_provider_name(self) -> str:
        """Return provider name."""
        return self._name

    @property
    def is_available(self) -> bool:
        """Return whether the provider is available."""
        return self._is_available


class BlockingSearchProvider(SearchProvider):
    """Provider that blocks until released so concurrent calls overlap."""

    def __init__(self, *, name: str = "blocking") -> None:
        self._name = name
        self.search_calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def search(self, query: str, options: SearchOptions | None = None) -> SearchResult:
        """Wait for release and then return one stable result."""
        del options
        self.search_calls += 1
        self.started.set()
        await self.release.wait()
        return SearchResult(
            query=query,
            provider=self._name,
            execution_time_ms=5,
            results=[build_search_result_item(f"{query}-1")],
        )

    def get_provider_name(self) -> str:
        """Return provider name."""
        return self._name


class TestSearchProviderInterface:
    """Tests for SearchProvider abstract interface."""

    @pytest.mark.asyncio
    async def test_provider_can_be_implemented(self) -> None:
        """Test that SearchProvider can be subclassed."""
        provider = MockSearchProvider()
        assert provider.get_provider_name() == "mock"

    @pytest.mark.asyncio
    async def test_search_returns_search_result(self) -> None:
        """Test that search returns SearchResult."""
        provider = MockSearchProvider()
        result = await provider.search("test query")

        assert isinstance(result, SearchResult)
        assert result.query == "test query"
        assert result.provider == "mock"
        assert len(result.results) == 10

    @pytest.mark.asyncio
    async def test_search_with_options(self) -> None:
        """Test search with custom options."""
        provider = MockSearchProvider()
        options = SearchOptions(max_results=5)
        result = await provider.search("test", options)

        assert len(result.results) == 5

    @pytest.mark.asyncio
    async def test_provider_tracks_calls(self) -> None:
        """Test that provider tracks search calls."""
        provider = MockSearchProvider()
        await provider.search("query 1")
        await provider.search("query 2")

        assert len(provider.search_calls) == 2
        assert provider.search_calls[0][0] == "query 1"
        assert provider.search_calls[1][0] == "query 2"

    def test_is_available_property(self) -> None:
        """Test is_available property."""
        provider = MockSearchProvider()
        assert provider.is_available is True

        provider.set_available(False)
        assert provider.is_available is False


class TestSearchProviderErrors:
    """Tests for search provider exceptions."""

    def test_search_provider_error(self) -> None:
        """Test SearchProviderError basics."""
        error = SearchProviderError("Test error", "test_provider", "test_query")
        assert str(error) == "Test error"
        assert error.provider == "test_provider"
        assert error.query == "test_query"

    def test_rate_limit_error(self) -> None:
        """Test RateLimitError with retry_after."""
        error = RateLimitError(
            "Rate limit exceeded",
            "tavily",
            "test query",
            retry_after=60,
        )
        assert error.provider == "tavily"
        assert error.retry_after == 60

    def test_authentication_error(self) -> None:
        """Test AuthenticationError."""
        error = AuthenticationError(
            "Invalid API key",
            "tavily",
            "test query",
        )
        assert error.provider == "tavily"
        assert isinstance(error, SearchProviderError)

    def test_network_error(self) -> None:
        """Test NetworkError with original error."""
        original = ConnectionError("Connection refused")
        error = NetworkError(
            "Network failure",
            "tavily",
            "test query",
            original_error=original,
        )
        assert error.provider == "tavily"
        assert error.original_error is original

    @pytest.mark.asyncio
    async def test_provider_can_raise_rate_limit_error(self) -> None:
        """Test provider raising RateLimitError."""
        provider = MockSearchProvider(
            should_fail=True,
            fail_with=RateLimitError("Rate limited", "mock", "test"),
        )

        with pytest.raises(RateLimitError) as exc_info:
            await provider.search("test")

        assert exc_info.value.retry_after is None

    @pytest.mark.asyncio
    async def test_provider_can_raise_authentication_error(self) -> None:
        """Test provider raising AuthenticationError."""
        provider = MockSearchProvider(
            should_fail=True,
            fail_with=AuthenticationError("Invalid key", "mock"),
        )

        with pytest.raises(AuthenticationError):
            await provider.search("test")


class TestSearchProviderPolymorphism:
    """Tests for polymorphic usage of SearchProvider."""

    @pytest.mark.asyncio
    async def test_multiple_providers_can_be_used_together(self) -> None:
        """Test using multiple providers polymorphically."""
        providers = [
            MockSearchProvider(name="provider_a"),
            MockSearchProvider(name="provider_b"),
            MockSearchProvider(name="provider_c"),
        ]

        results = []
        for provider in providers:
            result = await provider.search("test")
            results.append(result)

        assert len(results) == 3
        assert results[0].provider == "provider_a"
        assert results[1].provider == "provider_b"
        assert results[2].provider == "provider_c"

    @pytest.mark.asyncio
    async def test_provider_interface_contract(self) -> None:
        """Test that all providers follow the same contract."""
        provider: SearchProvider = MockSearchProvider()

        # Test required methods exist
        assert hasattr(provider, "search")
        assert hasattr(provider, "get_provider_name")
        assert hasattr(provider, "is_available")

        # Test search is async
        import inspect

        assert inspect.iscoroutinefunction(provider.search)

        # Test get_provider_name returns string
        name = provider.get_provider_name()
        assert isinstance(name, str)


class TestProviderResolution:
    """Tests for config-driven provider selection."""

    def test_resolve_provider_specs_expands_hybrid_mode(self) -> None:
        config = Config()
        config.search.mode = SearchMode.HYBRID_PARALLEL
        config.search.providers = ["tavily"]

        specs = resolve_provider_specs(config)

        assert [spec.provider_name for spec in specs] == ["tavily", "tavily_basic"]

    def test_resolve_provider_specs_preserves_explicit_basic_provider(self) -> None:
        config = Config()
        config.search.mode = SearchMode.TAVILY_PRIMARY
        config.search.providers = ["tavily_basic"]

        specs = resolve_provider_specs(config)

        assert [spec.provider_name for spec in specs] == ["tavily_basic"]


class TestCachedSearchProvider:
    """Tests for provider-layer search caching."""

    @pytest.mark.asyncio
    async def test_repeated_identical_searches_use_cached_results(self, tmp_path) -> None:
        """A cache hit should skip the wrapped provider."""
        wrapped = FixtureSearchProvider(name="tavily")
        provider = CachedSearchProvider(
            wrapped,
            store=SearchCacheStore(tmp_path / "search-cache.sqlite3"),
            ttl_seconds=300,
            in_flight_registry=InFlightSearchRegistry(),
            default_options=SearchOptions(search_depth=ResearchDepth.DEEP, max_results=10),
        )

        first = await provider.search("openai gpt-5", SearchOptions(max_results=2))
        second = await provider.search("openai gpt-5", SearchOptions(max_results=2))

        assert len(wrapped.search_calls) == 1
        # Results should be equivalent except for cache metadata
        assert first.query == second.query
        assert first.provider == second.provider
        assert first.results == second.results
        assert first.metadata["cache_status"] == "miss"
        assert second.metadata["cache_status"] == "hit"

    @pytest.mark.asyncio
    async def test_provider_errors_are_not_cached(self, tmp_path) -> None:
        """Failures should surface and leave the cache empty."""
        wrapped = FixtureSearchProvider(
            name="tavily",
            fail_with=SearchProviderError("boom", "tavily", "openai gpt-5"),
        )
        provider = CachedSearchProvider(
            wrapped,
            store=SearchCacheStore(tmp_path / "search-cache.sqlite3"),
            ttl_seconds=300,
            in_flight_registry=InFlightSearchRegistry(),
            default_options=SearchOptions(search_depth=ResearchDepth.DEEP, max_results=10),
        )

        with pytest.raises(SearchProviderError):
            await provider.search("openai gpt-5", SearchOptions(max_results=2))
        with pytest.raises(SearchProviderError):
            await provider.search("openai gpt-5", SearchOptions(max_results=2))

        assert len(wrapped.search_calls) == 2

    @pytest.mark.asyncio
    async def test_concurrent_identical_misses_share_one_in_flight_request(self, tmp_path) -> None:
        """Concurrent misses should collapse to a single upstream search."""
        wrapped = BlockingSearchProvider(name="tavily")
        provider = CachedSearchProvider(
            wrapped,
            store=SearchCacheStore(tmp_path / "search-cache.sqlite3"),
            ttl_seconds=300,
            in_flight_registry=InFlightSearchRegistry(),
            default_options=SearchOptions(search_depth=ResearchDepth.DEEP, max_results=10),
        )
        options = SearchOptions(max_results=2, search_depth=ResearchDepth.DEEP)

        first_task = asyncio.create_task(provider.search("openai gpt-5", options))
        await wrapped.started.wait()
        second_task = asyncio.create_task(provider.search("openai gpt-5", options))
        await asyncio.sleep(0)
        wrapped.release.set()

        first, second = await asyncio.gather(first_task, second_task)

        assert wrapped.search_calls == 1
        assert first == second


class TestProviderFactoryIntegration:
    """Tests that collection flows use the shared provider factory."""

    @pytest.mark.asyncio
    async def test_source_collector_initializes_providers_through_factory(self, monkeypatch) -> None:
        """Sequential collection should delegate provider construction to the factory."""
        config = Config()
        config.search.mode = SearchMode.HYBRID_PARALLEL
        config.search.providers = ["tavily"]

        captured_specs: list[list[str]] = []

        def fake_build_search_providers(
            current_config: Config,
            provider_specs: list[ProviderSpec],
            *,
            config_path=None,
        ) -> tuple[list[SearchProvider], list[str]]:
            assert current_config is config
            assert config_path is None
            captured_specs.append([spec.provider_name for spec in provider_specs])
            return [FixtureSearchProvider(name="tavily"), FixtureSearchProvider(name="tavily_basic")], []

        monkeypatch.setattr(
            "cc_deep_research.agents.source_collector.build_search_providers",
            fake_build_search_providers,
        )

        collector = SourceCollectorAgent(config)
        await collector.initialize_providers()

        assert captured_specs == [["tavily", "tavily_basic"]]
        assert collector.get_available_providers() == ["tavily", "tavily_basic"]
        await collector.close_providers()

    @pytest.mark.asyncio
    async def test_parallel_strategy_uses_shared_provider_factory(self, monkeypatch) -> None:
        """Parallel collection should request its Tavily provider through the shared factory."""
        config = Config()
        config.tavily.api_keys = ["test-key"]
        monitor = ResearchMonitor(enabled=False)
        session_state = OrchestratorSessionState(configured_providers=["tavily"])
        captured: list[tuple[str, int | None]] = []

        def fake_build_search_provider(
            current_config: Config,
            provider_spec: ProviderSpec,
            *,
            max_results_override: int | None = None,
            config_path=None,
        ) -> SearchProvider | None:
            assert current_config is config
            assert config_path is None
            captured.append((provider_spec.provider_name, max_results_override))
            return FixtureSearchProvider(name=provider_spec.provider_name)

        async def fake_execute_multiple_tasks(self, tasks, timeout=120.0):
            del self, timeout
            return [
                {
                    "task_id": task["task_id"],
                    "query": task["query"],
                    "status": "success",
                    "sources": [build_search_result_item(task["task_id"])],
                    "source_count": 1,
                    "execution_time_ms": 10,
                }
                for task in tasks
            ]

        monkeypatch.setattr(
            "cc_deep_research.orchestration.source_collection_parallel.build_search_provider",
            fake_build_search_provider,
        )
        monkeypatch.setattr(
            "cc_deep_research.agents.researcher.ResearcherAgent.execute_multiple_tasks",
            fake_execute_multiple_tasks,
        )

        strategy = ParallelSourceCollectionStrategy(
            config=config,
            monitor=monitor,
            session_state=session_state,
            num_researchers=2,
            hydrate_sources=lambda sources, _depth: asyncio.sleep(0, result=sources),
            aggregate_sources=lambda sources: sources,
        )

        sources = await strategy.collect(
            agent_pool=object(),
            query_families=[
                QueryFamily(query="query one", family="baseline", intent_tags=["baseline"]),
                QueryFamily(query="query two", family="baseline", intent_tags=["baseline"]),
            ],
            depth=ResearchDepth.DEEP,
            min_sources=4,
        )

        assert captured == [("tavily", 2)]
        assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_parallel_strategy_raises_timeout_error_when_all_tasks_timeout(
        self,
        monkeypatch,
    ) -> None:
        """Parallel collection should surface a single timeout failure when every task times out."""
        config = Config()
        config.tavily.api_keys = ["test-key"]
        monitor = ResearchMonitor(enabled=False)
        session_state = OrchestratorSessionState(configured_providers=["tavily"])

        def fake_build_search_provider(
            current_config: Config,
            provider_spec: ProviderSpec,
            *,
            max_results_override: int | None = None,
            config_path=None,
        ) -> SearchProvider | None:
            del max_results_override, config_path
            assert current_config is config
            assert provider_spec.provider_name == "tavily"
            return FixtureSearchProvider(name="tavily")

        async def fake_execute_multiple_tasks(self, tasks, timeout=120.0):
            del self
            return [
                {
                    "task_id": task["task_id"],
                    "query": task["query"],
                    "status": "timeout",
                    "error": f"Execution timed out after {timeout}s",
                    "sources": [],
                    "source_count": 0,
                }
                for task in tasks
            ]

        monkeypatch.setattr(
            "cc_deep_research.orchestration.source_collection_parallel.build_search_provider",
            fake_build_search_provider,
        )
        monkeypatch.setattr(
            "cc_deep_research.agents.researcher.ResearcherAgent.execute_multiple_tasks",
            fake_execute_multiple_tasks,
        )

        strategy = ParallelSourceCollectionStrategy(
            config=config,
            monitor=monitor,
            session_state=session_state,
            num_researchers=2,
            hydrate_sources=lambda sources, _depth: asyncio.sleep(0, result=sources),
            aggregate_sources=lambda sources: sources,
        )

        with pytest.raises(ParallelCollectionTimeoutError):
            await strategy.collect(
                agent_pool=object(),
                query_families=[
                    QueryFamily(query="query one", family="baseline", intent_tags=["baseline"]),
                    QueryFamily(query="query two", family="baseline", intent_tags=["baseline"]),
                ],
                depth=ResearchDepth.DEEP,
                min_sources=4,
            )

        timeout_policy_event = next(
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "decision.made"
            and event["metadata"]["decision_type"] == "timeout_policy"
        )
        assert timeout_policy_event["metadata"]["inputs"]["scope"] == "parallel_collection.researcher_task"

    @pytest.mark.asyncio
    async def test_source_collection_service_falls_back_to_sequential_after_parallel_timeout(
        self,
    ) -> None:
        """Parallel timeout should fall back to the sequential collector when enabled."""
        config = Config()
        config.search_team.fallback_to_sequential = True
        monitor = ResearchMonitor(enabled=False)
        session_state = OrchestratorSessionState(configured_providers=["tavily"], monitor=monitor)
        collection = SourceCollectionService(
            config=config,
            monitor=monitor,
            session_state=session_state,
            num_researchers=2,
        )

        async def fake_parallel_collect(**kwargs):
            del kwargs
            raise ParallelCollectionTimeoutError("parallel researchers timed out")

        async def fake_sequential_collect(**kwargs):
            del kwargs
            return expected

        expected = [build_search_result_item("sequential-fallback")]
        collection._parallel.collect = fake_parallel_collect
        collection._sequential.collect = fake_sequential_collect

        sources = await collection.collect_with_fallback(
            collector=object(),
            agent_pool=object(),
            query_families=[QueryFamily(query="query one", family="baseline", intent_tags=["baseline"])],
            depth=ResearchDepth.STANDARD,
            min_sources=3,
            prefer_parallel=True,
        )

        assert sources == expected
        fallback_event = next(
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "decision.made"
            and event["metadata"]["decision_type"] == "collection_fallback"
        )
        assert fallback_event["metadata"]["chosen_option"] == "sequential"


class TestSourceCollectorDegradation:
    """Tests for graceful fallback behavior in source collection."""

    @pytest.mark.asyncio
    async def test_initialize_providers_adds_basic_tavily_in_hybrid_mode(self) -> None:
        config = Config()
        config.search.mode = SearchMode.HYBRID_PARALLEL
        config.search.providers = ["tavily"]
        config.tavily.api_keys = ["test-key"]

        collector = SourceCollectorAgent(config)
        await collector.initialize_providers()

        assert collector.get_available_providers() == ["tavily", "tavily_basic"]
        await collector.close_providers()

    @pytest.mark.asyncio
    async def test_collect_sources_returns_empty_when_no_provider_is_available(self) -> None:
        config = Config()
        config.search.providers = ["tavily"]

        collector = SourceCollectorAgent(config)

        sources = await collector.collect_sources("test query", SearchOptions(max_results=2))

        assert sources == []
        assert collector.get_provider_warnings() == [
            "Provider 'tavily' is selected but no Tavily API keys are configured."
        ]

    @pytest.mark.asyncio
    async def test_collect_sources_returns_empty_when_all_providers_fail(self) -> None:
        config = Config()
        collector = SourceCollectorAgent(config)
        collector._providers = [
            MockSearchProvider(
                name="provider_a",
                should_fail=True,
                fail_with=SearchProviderError("boom", "provider_a", "test query"),
            ),
            MockSearchProvider(
                name="provider_b",
                should_fail=True,
                fail_with=NetworkError("down", "provider_b", "test query"),
            ),
        ]

        sources = await collector.collect_sources("test query", SearchOptions(max_results=2))

        assert sources == []
        assert collector.get_provider_warnings() == [
            "All initialized providers failed for query 'test query'. Continuing with an empty result set from: provider_a, provider_b."
        ]

    @pytest.mark.asyncio
    async def test_collect_sources_degrades_cleanly_on_auth_rate_limit_and_timeout_failures(
        self,
    ) -> None:
        """Provider auth, rate-limit, and timeout failures should not crash collection."""
        config = Config()
        collector = SourceCollectorAgent(config)
        collector._providers = [
            MockSearchProvider(
                name="provider_auth",
                should_fail=True,
                fail_with=AuthenticationError("invalid key", "provider_auth", "test query"),
            ),
            MockSearchProvider(
                name="provider_rate_limit",
                should_fail=True,
                fail_with=RateLimitError(
                    "rate limited",
                    "provider_rate_limit",
                    "test query",
                    retry_after=30,
                ),
            ),
            MockSearchProvider(
                name="provider_timeout",
                should_fail=True,
                fail_with=NetworkError("request timed out", "provider_timeout", "test query"),
            ),
        ]

        sources = await collector.collect_sources("test query", SearchOptions(max_results=2))

        assert sources == []
        assert collector.get_provider_warnings() == [
            "All initialized providers failed for query 'test query'. Continuing with an empty result set from: provider_auth, provider_rate_limit, provider_timeout."
        ]

    @pytest.mark.asyncio
    async def test_collect_sources_treats_empty_valid_results_as_success(self) -> None:
        """An empty but valid provider response should avoid the all-failed degradation path."""
        config = Config()
        collector = SourceCollectorAgent(config)
        collector._providers = [
            FixtureSearchProvider(
                name="provider_empty",
                results_by_query={"test query": []},
            ),
            MockSearchProvider(
                name="provider_timeout",
                should_fail=True,
                fail_with=NetworkError("request timed out", "provider_timeout", "test query"),
            ),
        ]

        sources = await collector.collect_sources("test query", SearchOptions(max_results=2))

        assert sources == []
        assert collector.get_provider_warnings() == []


class TestSourceProvenanceAggregation:
    """Tests for provenance preservation during aggregation."""

    def test_deduplicate_by_url_merges_query_provenance(self) -> None:
        """Duplicate URLs from different query families should retain both origins."""
        baseline = SearchResultItem(
            url="https://example.com/shared",
            title="Shared result",
            score=0.6,
            source_metadata={"provider": "mock"},
            query_provenance=[
                {
                    "query": "market structure",
                    "family": "baseline",
                    "intent_tags": ["baseline", "informational"],
                }
            ],
        )
        primary_source = SearchResultItem(
            url="https://example.com/shared/",
            title="Shared result better",
            snippet="Longer snippet",
            score=0.9,
            query_provenance=[
                {
                    "query": "market structure official guidance",
                    "family": "primary-source",
                    "intent_tags": ["primary-source", "evidence"],
                }
            ],
        )

        deduplicated = deduplicate_by_url([baseline, primary_source])

        assert len(deduplicated) == 1
        merged = deduplicated[0]
        assert merged.score == 0.9
        assert merged.title == "Shared result better"
        assert [entry.family for entry in merged.query_provenance] == [
            "primary-source",
            "baseline",
        ]
        assert merged.source_metadata["query_families"] == [
            "primary-source",
            "baseline",
        ]


class TestSourceCollectionFixtureIntegration:
    """Integration tests for source collection with fixture-backed providers.

    These tests exercise the real source collection layer with replayed provider
    payloads, verifying provenance propagation, deduplication, and degraded
    provider availability handling.
    """

    @pytest.mark.asyncio
    async def test_source_aggregation_with_replayed_provider_payloads(self) -> None:
        """Real aggregation path with fixture-backed provider results."""
        monitor = ResearchMonitor(enabled=False)
        aggregation = SourceAggregationService(monitor=monitor)

        baseline_sources = [
            SearchResultItem(
                url="https://example.com/article1",
                title="Article 1",
                snippet="Baseline snippet",
                score=0.8,
            ),
            SearchResultItem(
                url="https://example.com/article2",
                title="Article 2",
                snippet="Another baseline",
                score=0.7,
            ),
        ]
        for source in baseline_sources:
            source.add_query_provenance(
                query="quantum computing basics",
                family="baseline",
                intent_tags=["baseline", "informational"],
            )

        primary_sources = [
            SearchResultItem(
                url="https://example.com/article1",
                title="Article 1 Primary",
                snippet="Primary source version",
                score=0.95,
            ),
            SearchResultItem(
                url="https://example.com/article3",
                title="Article 3",
                snippet="Primary only",
                score=0.85,
            ),
        ]
        for source in primary_sources:
            source.add_query_provenance(
                query="quantum computing official guidance",
                family="primary-source",
                intent_tags=["primary-source", "evidence"],
            )

        merged = aggregation.merge_sources(
            existing_sources=baseline_sources,
            new_sources=primary_sources,
        )

        assert len(merged) == 3
        article1 = next(s for s in merged if "article1" in s.url)
        assert article1.score == 0.95
        families = {entry.family for entry in article1.query_provenance}
        assert families == {"baseline", "primary-source"}

    @pytest.mark.asyncio
    async def test_parallel_aggregation_with_replayed_payloads(self) -> None:
        """Parallel source aggregation with fixture-backed provider payloads."""
        monitor = ResearchMonitor(enabled=False)
        aggregation = SourceAggregationService(monitor=monitor)

        sources = [
            SearchResultItem(
                url=f"https://example.com/source{i}",
                title=f"Source {i}",
                snippet=f"Content {i}",
                score=0.9 - (i * 0.1),
            )
            for i in range(5)
        ]
        for i, source in enumerate(sources):
            source.add_query_provenance(
                query=f"query variation {i}",
                family=f"family-{i}",
                intent_tags=[f"tag-{i}"],
            )

        aggregated = aggregation.aggregate_parallel_sources(sources)

        assert len(aggregated) == 5
        assert aggregated[0].score == 0.9
        assert all(s.query_provenance for s in aggregated)

    @pytest.mark.asyncio
    async def test_source_limit_preserves_provenance_metadata(self) -> None:
        """Source limiting preserves query provenance through the cut."""
        monitor = ResearchMonitor(enabled=False)
        aggregation = SourceAggregationService(monitor=monitor)

        sources = [
            SearchResultItem(
                url=f"https://example.com/page{i}",
                title=f"Page {i}",
                snippet=f"Info {i}",
                score=max(0.0, 1.0 - (i * 0.1)),
            )
            for i in range(20)
        ]
        for i, source in enumerate(sources):
            source.add_query_provenance(
                query=f"topic {i}",
                family="mixed-families",
                intent_tags=["test"],
            )

        limited, was_limited = aggregation.apply_source_limit(
            sources=sources,
            limit=10,
            query="test query",
        )

        assert len(limited) == 10
        assert was_limited is True
        assert all(s.query_provenance for s in limited)
        for source in limited:
            assert len(source.query_provenance) > 0
            assert source.query_provenance[0].query.startswith("topic")

    @pytest.mark.asyncio
    async def test_degraded_provider_availability_with_stable_session_metadata(self) -> None:
        """Degraded provider paths produce stable session metadata."""
        config = Config()
        config.search.providers = ["tavily"]

        monitor = ResearchMonitor(enabled=False)
        session_state = OrchestratorSessionState(
            configured_providers=["tavily"],
        )

        collection = SourceCollectionService(
            config=config,
            monitor=monitor,
            session_state=session_state,
            num_researchers=2,
        )

        query_families = [
            QueryFamily(query="test query", family="baseline", intent_tags=["baseline"]),
        ]

        class DegradedCollector:
            def __init__(self) -> None:
                self._providers: list[SearchProvider] = []
                self._warnings: list[str] = []

            async def initialize_providers(self) -> None:
                pass

            def get_provider_warnings(self) -> list[str]:
                return ["Provider degraded - using fallback mode"]

            def get_available_providers(self) -> list[str]:
                return ["fallback"]

            async def collect_sources(
                self,
                query: str,
                options: SearchOptions,
                query_family: QueryFamily | None = None,
            ) -> list[SearchResultItem]:
                del self, query, options, query_family
                return []

            async def collect_multiple_queries(
                self,
                queries: list[str],
                options: SearchOptions,
                query_families: list[QueryFamily] | None = None,
            ) -> list[SearchResultItem]:
                del self, queries, options, query_families
                return []

            async def close_providers(self) -> None:
                pass

        collector = DegradedCollector()
        await collection.collect_sources(
            collector=collector,
            query_families=query_families,
            depth=ResearchDepth.STANDARD,
        )

        provider_meta = session_state.provider_metadata
        assert provider_meta["available"] == ["fallback"]
        assert len(provider_meta["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_search_result_item_data_fails_validation(self) -> None:
        """Test that structurally invalid SearchResultItem data is caught."""
        from pydantic_core import ValidationError

        with pytest.raises(ValidationError):
            SearchResultItem(
                url="",
                title="Invalid",
                snippet="Missing URL",
                score=0.5,
            )

    @pytest.mark.asyncio
    async def test_empty_source_list_produces_valid_empty_result(self) -> None:
        """Empty source list from collection produces stable metadata."""
        monitor = ResearchMonitor(enabled=False)
        aggregation = SourceAggregationService(monitor=monitor)

        result = aggregation.merge_sources(
            existing_sources=[],
            new_sources=[],
        )

        assert result == []
        limited, was_limited = aggregation.apply_source_limit(
            sources=[],
            limit=10,
            query="empty test",
        )

        assert limited == []
        assert was_limited is False


class TestSourceCollectionWithResultAggregator:
    """Tests for ResultAggregator with query family metadata."""

    @pytest.mark.asyncio
    async def test_aggregator_tracks_query_families_across_results(self) -> None:
        """ResultAggregator preserves query family provenance across multiple results."""
        aggregator = ResultAggregator(deduplicate=True, sort_by_score=True, monitor=False)

        families = [
            QueryFamily(query="climate policy", family="baseline", intent_tags=["informational"]),
            QueryFamily(
                query="climate policy official",
                family="primary-source",
                intent_tags=["evidence"],
            ),
            QueryFamily(
                query="climate policy analysis",
                family="expert-analysis",
                intent_tags=["analysis"],
            ),
        ]

        for family in families:
            item = SearchResultItem(
                url=f"https://example.com/{family.family}",
                title=f"Result from {family.family}",
                snippet=f"Snippet for {family.family}",
                score=0.8,
            )
            item.add_query_provenance(
                query=family.query,
                family=family.family,
                intent_tags=list(family.intent_tags),
            )
            result = SearchResult(
                query=family.query,
                results=[item],
                provider="test",
            )
            aggregator.add_result(result)

        aggregated = aggregator.get_aggregated()

        assert len(aggregated) == 3
        for item in aggregated:
            assert len(item.query_provenance) > 0

    @pytest.mark.asyncio
    async def test_aggregator_deduplication_preserves_all_provenance(self) -> None:
        """Deduplication merges provenance while preserving all contributing families."""
        aggregator = ResultAggregator(deduplicate=True, sort_by_score=True, monitor=False)

        item1 = SearchResultItem(
            url="https://example.com/duplicate",
            title="First version",
            snippet="First",
            score=0.7,
        )
        item1.add_query_provenance(
            query="baseline query",
            family="baseline",
            intent_tags=["informational"],
        )
        result1 = SearchResult(
            query="baseline query",
            results=[item1],
            provider="provider1",
        )

        item2 = SearchResultItem(
            url="https://example.com/duplicate/",
            title="Better version",
            snippet="Better content here",
            score=0.9,
        )
        item2.add_query_provenance(
            query="primary query",
            family="primary-source",
            intent_tags=["evidence"],
        )
        result2 = SearchResult(
            query="primary query",
            results=[item2],
            provider="provider2",
        )

        aggregator.add_result(result1)
        aggregator.add_result(result2)

        aggregated = aggregator.get_aggregated()

        assert len(aggregated) == 1
        merged = aggregated[0]
        assert merged.score == 0.9
        families = [entry.family for entry in merged.query_provenance]
        assert "baseline" in families
        assert "primary-source" in families
