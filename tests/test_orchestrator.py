"""Contract tests for TeamResearchOrchestrator."""

from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

from cc_deep_research.agents import (
    AGENT_TYPE_ANALYZER,
    AGENT_TYPE_COLLECTOR,
    AGENT_TYPE_DEEP_ANALYZER,
    AGENT_TYPE_EXPANDER,
    AGENT_TYPE_LEAD,
    AGENT_TYPE_VALIDATOR,
)
from cc_deep_research.agents.query_expander import QueryExpanderAgent
from cc_deep_research.aggregation import deduplicate_by_url
from cc_deep_research.cli import _resolve_parallel_mode_override, main
from cc_deep_research.config import Config
from cc_deep_research.coordination.agent_pool import LocalAgentPool
from cc_deep_research.coordination.message_bus import LocalMessageBus
from cc_deep_research.models import (
    AnalysisFinding,
    AnalysisGap,
    AnalysisResult,
    IterationHistoryRecord,
    QueryFamily,
    ResearchDepth,
    SearchOptions,
    SearchResultItem,
    StrategyPlan,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration import OrchestratorRuntimeState
from cc_deep_research.orchestrator import TeamExecutionError, TeamResearchOrchestrator
from cc_deep_research.teams import LocalResearchTeam


def _make_strategy(query: str, depth: ResearchDepth, query_variations: int) -> StrategyResult:
    """Build a stable strategy result for workflow tests."""
    return StrategyResult(
        query=query,
        complexity="moderate",
        depth=depth,
        profile={
            "intent": "informational",
            "is_time_sensitive": False,
            "key_terms": query.split(),
            "target_source_classes": ["official_docs"],
        },
        strategy=StrategyPlan(
            query_variations=query_variations,
            max_sources=12,
            enable_cross_ref=depth == ResearchDepth.DEEP,
            enable_quality_scoring=True,
            tasks=["collect", "analyze", "report"],
            intent="informational",
            time_sensitive=False,
            key_terms=query.split(),
            target_source_classes=["official_docs"],
        ),
        tasks_needed=["collect", "analyze", "report"],
    )


def _make_analysis(
    *,
    source_count: int,
    analysis_method: str = "ai_semantic",
    deep_analysis_complete: bool = False,
    gaps: Sequence[AnalysisGap | str] | None = None,
) -> AnalysisResult:
    """Build a compact analysis payload."""
    return AnalysisResult(
        key_findings=[AnalysisFinding(title="Finding", description="Description")],
        themes=["Theme"],
        gaps=list(gaps or []),
        analysis_method=analysis_method,
        deep_analysis_complete=deep_analysis_complete,
        source_count=source_count,
    )


def _make_validation(
    *,
    quality_score: float = 0.82,
    needs_follow_up: bool = False,
    follow_up_queries: Sequence[str] | None = None,
    failure_modes: Sequence[str] | None = None,
    evidence_diagnosis: str = "unknown",
) -> ValidationResult:
    """Build a validation payload."""
    return ValidationResult(
        quality_score=quality_score,
        is_valid=not needs_follow_up,
        issues=[],
        warnings=[],
        recommendations=[],
        failure_modes=list(failure_modes or []),
        evidence_diagnosis=evidence_diagnosis,
        needs_follow_up=needs_follow_up,
        follow_up_queries=list(follow_up_queries or []),
        target_source_count=3,
    )


def _make_sources(prefix: str, count: int) -> list[SearchResultItem]:
    """Build stable source lists with unique URLs."""
    return [
        SearchResultItem(
            url=f"https://example.com/{prefix}-{index}",
            title=f"{prefix} title {index}",
            snippet=f"{prefix} snippet {index}",
            score=max(0.1, 1.0 - (index * 0.05)),
        )
        for index in range(1, count + 1)
    ]


class FakeLeadAgent:
    """Strategy fixture that varies query expansion by depth."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ResearchDepth]] = []

    def analyze_query(self, query: str, depth: ResearchDepth) -> StrategyResult:
        self.calls.append((query, depth))
        variations = {
            ResearchDepth.QUICK: 1,
            ResearchDepth.STANDARD: 3,
            ResearchDepth.DEEP: 4,
        }[depth]
        return _make_strategy(query, depth, variations)


class FakeExpanderAgent:
    """Query-expansion fixture with deterministic outputs."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def expand_query(
        self,
        query: str,
        depth: ResearchDepth,
        *,
        max_variations: int,
        strategy: dict[str, object],
    ) -> list[QueryFamily]:
        self.calls.append(
            {
                "query": query,
                "depth": depth,
                "max_variations": max_variations,
                "strategy": strategy,
            }
        )
        variants = [
            QueryFamily(query=query, family="baseline", intent_tags=["baseline", "informational"]),
            QueryFamily(
                query=f"{query} official guidance",
                family="primary-source",
                intent_tags=["primary-source", "informational", "evidence"],
            ),
            QueryFamily(
                query=f"{query} expert analysis",
                family="expert-analysis",
                intent_tags=["expert-analysis", "informational", "analysis"],
            ),
            QueryFamily(
                query=f"{query} risks criticism",
                family="risk",
                intent_tags=["risk", "informational", "risk-review"],
            ),
        ]
        return variants[:max_variations]


class FakeCollectorAgent:
    """Source-collection fixture used by execute_research contract tests."""

    def __init__(
        self,
        *,
        available: list[str],
        warnings: list[str],
        results_by_query: dict[str, list[SearchResultItem]] | None = None,
    ) -> None:
        self._available = available
        self._warnings = warnings
        self._results_by_query = results_by_query or {}
        self.initialized = False
        self.closed = False
        self.single_calls: list[tuple[str, SearchOptions]] = []
        self.multi_calls: list[tuple[list[str], SearchOptions]] = []

    async def initialize_providers(self) -> None:
        self.initialized = True

    def get_provider_warnings(self) -> list[str]:
        return list(self._warnings)

    def get_available_providers(self) -> list[str]:
        return list(self._available)

    async def collect_sources(
        self,
        query: str,
        options: SearchOptions,
        query_family: QueryFamily | None = None,
    ) -> list[SearchResultItem]:
        self.single_calls.append((query, options))
        return self._annotate_sources(
            self._get_results_for_query(query),
            query_family or QueryFamily(query=query),
        )

    async def collect_multiple_queries(
        self,
        queries: list[str],
        options: SearchOptions,
        query_families: list[QueryFamily] | None = None,
    ) -> list[SearchResultItem]:
        self.multi_calls.append((list(queries), options))
        merged: list[SearchResultItem] = []
        families_by_query = {family.query: family for family in query_families or []}
        for query in queries:
            family = families_by_query.get(query, QueryFamily(query=query))
            for source in self._annotate_sources(self._get_results_for_query(query), family):
                merged.append(source)
        return deduplicate_by_url(merged)

    async def close_providers(self) -> None:
        self.closed = True

    def _get_results_for_query(self, query: str) -> list[SearchResultItem]:
        if query in self._results_by_query:
            sources = self._results_by_query[query]
        else:
            slug = query.lower().replace(" ", "-")
            sources = _make_sources(slug, 2)
        return [source.model_copy(deep=True) for source in sources]

    def _annotate_sources(
        self,
        sources: list[SearchResultItem],
        family: QueryFamily,
    ) -> list[SearchResultItem]:
        """Apply query provenance to fake collector results."""
        annotated: list[SearchResultItem] = []
        for source in sources:
            source.add_query_provenance(
                query=family.query,
                family=family.family,
                intent_tags=list(family.intent_tags),
            )
            annotated.append(source)
        return annotated


class FakeAnalyzerAgent:
    """Analysis fixture for deterministic synthesis output."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[SearchResultItem], str]] = []

    def analyze_sources(self, sources: list[SearchResultItem], query: str) -> AnalysisResult:
        self.calls.append((list(sources), query))
        return _make_analysis(source_count=len(sources))


class FakeDeepAnalyzerAgent:
    """Deep-analysis fixture that marks the deep phase complete."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[SearchResultItem], str]] = []

    def deep_analyze(self, sources: list[SearchResultItem], query: str) -> dict[str, object]:
        """Return a dict like the real DeepAnalyzerAgent.deep_analyze does."""
        self.calls.append((list(sources), query))
        return {
            "themes": ["Deep Theme"],
            "themes_detailed": [],
            "patterns": [],
            "consensus_points": [],
            "disagreement_points": [],
            "cross_reference_claims": [],
            "gaps": [],
            "key_findings": [],
            "implications": [],
            "comprehensive_synthesis": "",
            "analysis_passes": 3,
            "source_count": len(sources),
            "analysis_method": "multi_pass",
            "deep_analysis_complete": True,
        }


class FakeValidatorAgent:
    """Validation fixture that returns a ready-to-use contract payload."""

    def __init__(self, validation: ValidationResult | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._validation = validation or _make_validation()

    def validate_research(
        self,
        session: object,
        analysis: AnalysisResult,
        *,
        query: str,
        min_sources_override: int,
    ) -> ValidationResult:
        self.calls.append(
            {
                "session": session,
                "analysis": analysis,
                "query": query,
                "min_sources_override": min_sources_override,
            }
        )
        return self._validation.model_copy(deep=True)


def test_local_runtime_types_use_explicit_local_names() -> None:
    """Test that runtime-facing helper types are imported via their local names."""
    runtime_state = OrchestratorRuntimeState(
        team=MagicMock(spec=LocalResearchTeam),
        agents={},
        message_bus=MagicMock(spec=LocalMessageBus),
        agent_pool=MagicMock(spec=LocalAgentPool),
    )

    assert runtime_state.team is not None
    assert runtime_state.message_bus is not None
    assert runtime_state.agent_pool is not None


def _install_fake_team(
    orchestrator: TeamResearchOrchestrator,
    *,
    collector: FakeCollectorAgent,
    validator: FakeValidatorAgent | None = None,
    lead: FakeLeadAgent | None = None,
    expander: FakeExpanderAgent | None = None,
    analyzer: FakeAnalyzerAgent | None = None,
    deep_analyzer: FakeDeepAnalyzerAgent | None = None,
) -> dict[str, object]:
    """Install fake agents while keeping the real orchestrator workflow."""
    lead = lead or FakeLeadAgent()
    expander = expander or FakeExpanderAgent()
    analyzer = analyzer or FakeAnalyzerAgent()
    deep_analyzer = deep_analyzer or FakeDeepAnalyzerAgent()
    validator = validator or FakeValidatorAgent()

    async def initialize_team() -> None:
        orchestrator._agents = {
            AGENT_TYPE_LEAD: lead,
            AGENT_TYPE_COLLECTOR: collector,
            AGENT_TYPE_EXPANDER: expander,
            AGENT_TYPE_ANALYZER: analyzer,
            AGENT_TYPE_DEEP_ANALYZER: deep_analyzer,
            AGENT_TYPE_VALIDATOR: validator,
        }

    async def fetch_content(
        sources: list[SearchResultItem],
        _depth: ResearchDepth,
    ) -> list[SearchResultItem]:
        for source in sources:
            source.content = source.content or ("x" * 600)
        return sources

    orchestrator._initialize_team = initialize_team
    orchestrator._fetch_content_for_top_sources = AsyncMock(side_effect=fetch_content)
    orchestrator._shutdown_team = AsyncMock()
    orchestrator._monitor.set_session = MagicMock()

    return {
        "lead": lead,
        "expander": expander,
        "collector": collector,
        "analyzer": analyzer,
        "deep_analyzer": deep_analyzer,
        "validator": validator,
    }


class TestTeamResearchOrchestrator:
    """Workflow contract tests for the orchestrator."""

    def test_research_help_describes_no_team_as_sequential_collection(self) -> None:
        runner = CliRunner()

        result = runner.invoke(main, ["research", "--help"])

        assert result.exit_code == 0
        assert "[markdown|json|html]" in result.output
        assert "--no-team" in result.output
        assert "Run source collection sequentially instead of" in result.output
        assert "using parallel researchers" in result.output

    def test_no_team_override_forces_sequential_collection(self) -> None:
        assert _resolve_parallel_mode_override(no_team=True, parallel_mode=False) is False
        assert _resolve_parallel_mode_override(no_team=True, parallel_mode=True) is False
        assert _resolve_parallel_mode_override(no_team=False, parallel_mode=True) is True
        assert _resolve_parallel_mode_override(no_team=False, parallel_mode=False) is None

    def test_orchestrator_initialization(self) -> None:
        config = Config()
        monitor = ResearchMonitor(enabled=False)

        orchestrator = TeamResearchOrchestrator(config, monitor)

        assert orchestrator._config == config
        assert orchestrator._monitor == monitor
        assert orchestrator._team is None
        assert orchestrator._runtime_state is None

    @pytest.mark.asyncio
    async def test_initialize_team_uses_concrete_local_runtime_state(self) -> None:
        config = Config()
        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))

        await orchestrator._initialize_team()

        assert isinstance(orchestrator._runtime_state, OrchestratorRuntimeState)
        assert orchestrator._team is orchestrator._runtime_state.team
        assert orchestrator._team is not None
        assert orchestrator._team.is_active is True
        assert set(orchestrator._agents) == {
            AGENT_TYPE_LEAD,
            AGENT_TYPE_COLLECTOR,
            AGENT_TYPE_EXPANDER,
            AGENT_TYPE_ANALYZER,
            AGENT_TYPE_DEEP_ANALYZER,
            AGENT_TYPE_VALIDATOR,
        }
        assert orchestrator._message_bus is orchestrator._runtime_state.message_bus
        assert orchestrator._message_bus is not None
        assert orchestrator._message_bus.is_active is True
        assert orchestrator._agent_pool is not None
        assert orchestrator._agent_pool.is_active is True
        assert orchestrator._runtime_state.llm_registry is not None
        assert orchestrator._runtime_state.llm_router is not None
        assert orchestrator._planning._registry is orchestrator._runtime_state.llm_registry

    def test_llm_router_events_update_session_metadata(self) -> None:
        """Routed LLM execution should flow into session metadata summaries."""
        orchestrator = TeamResearchOrchestrator(Config(), ResearchMonitor(enabled=False))
        orchestrator._reset_session_metadata_state()

        orchestrator._handle_llm_router_event(
            {
                "event_type": "route_fallback",
                "agent_id": "analyzer",
                "original_transport": "claude_cli",
                "fallback_transport": "openrouter_api",
                "reason": "primary_route_unavailable_or_failed",
            }
        )
        orchestrator._handle_llm_router_event(
            {
                "event_type": "route_completion",
                "agent_id": "analyzer",
                "transport": "openrouter_api",
                "provider": "openrouter",
                "model": "anthropic/claude-sonnet-4",
                "success": True,
                "latency_ms": 120,
                "prompt_tokens": 10,
                "completion_tokens": 25,
            }
        )

        llm_routes = orchestrator._session_state.get_llm_route_summary()
        assert llm_routes["actual_routes"]["analyzer"]["transport"] == "openrouter_api"
        assert llm_routes["usage_stats"]["analyzer:openrouter_api"]["total_tokens"] == 35
        assert llm_routes["fallback_count"] == 1

    @pytest.mark.asyncio
    async def test_shutdown_team_clears_local_runtime_state(self) -> None:
        config = Config()
        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))
        await orchestrator._initialize_team()

        team = orchestrator._team
        message_bus = orchestrator._message_bus
        agent_pool = orchestrator._agent_pool
        runtime_state = orchestrator._runtime_state

        await orchestrator._shutdown_team()

        assert runtime_state is not None
        assert team is not None
        assert message_bus is not None
        assert agent_pool is not None
        assert team.is_active is False
        assert message_bus.is_active is False
        assert agent_pool.is_active is False
        assert orchestrator._runtime_state is None
        assert orchestrator._team is None
        assert orchestrator._agents == {}
        assert orchestrator._message_bus is None
        assert orchestrator._agent_pool is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("depth", "expected_query_count", "expected_max_results", "deep_status"),
        [
            (ResearchDepth.QUICK, 1, 3, "not_requested"),
            (ResearchDepth.STANDARD, 3, 10, "not_requested"),
            (ResearchDepth.DEEP, 4, 50, "completed"),
        ],
    )
    async def test_execute_research_contract_by_depth(
        self,
        depth: ResearchDepth,
        expected_query_count: int,
        expected_max_results: int,
        deep_status: str,
    ) -> None:
        config = Config()
        config.search.providers = ["tavily"]
        config.search_team.parallel_execution = False

        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))
        collector = FakeCollectorAgent(available=["tavily"], warnings=[])
        fixtures = _install_fake_team(orchestrator, collector=collector)

        session = await orchestrator.execute_research(
            query="climate policy",
            depth=depth,
            min_sources=2,
        )

        assert session.query == "climate policy"
        assert session.metadata["providers"]["status"] == "ready"
        assert session.metadata["execution"]["degraded"] is False
        assert session.metadata["deep_analysis"]["status"] == deep_status
        assert session.metadata["strategy"]["profile"]["intent"] == "informational"
        assert session.metadata["strategy"]["strategy"]["target_source_classes"] == [
            "official_docs"
        ]
        query_families = session.metadata["strategy"]["strategy"]["query_families"]
        assert query_families[0]["family"] == "baseline"
        assert "informational" in query_families[0]["intent_tags"]
        assert len(session.metadata["iteration_history"]) == 1
        assert len(session.sources) == expected_query_count * 2

        if depth == ResearchDepth.QUICK:
            assert collector.single_calls[0][0] == "climate policy"
            assert collector.multi_calls == []
            assert fixtures["expander"].calls == []
        else:
            expanded_queries, options = collector.multi_calls[0]
            assert len(expanded_queries) == expected_query_count
            assert fixtures["expander"].calls[0]["max_variations"] == expected_query_count
            assert options.max_results == expected_max_results

        if collector.single_calls:
            assert collector.single_calls[0][1].search_depth == depth
            assert collector.single_calls[0][1].max_results == expected_max_results
        if collector.multi_calls:
            assert collector.multi_calls[0][1].search_depth == depth
            assert collector.multi_calls[0][1].max_results == expected_max_results

        if depth == ResearchDepth.DEEP:
            assert len(fixtures["deep_analyzer"].calls) == 1
        else:
            assert fixtures["deep_analyzer"].calls == []

    @pytest.mark.asyncio
    async def test_query_expansion_persists_family_metadata_and_uses_query_texts_for_collection(
        self,
    ) -> None:
        config = Config()
        config.search.providers = ["tavily"]
        config.search_team.parallel_execution = False

        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))
        collector = FakeCollectorAgent(available=["tavily"], warnings=[])
        fixtures = _install_fake_team(orchestrator, collector=collector)

        session = await orchestrator.execute_research(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            min_sources=2,
        )

        stored_families = session.metadata["strategy"]["strategy"]["query_families"]
        assert [family["family"] for family in stored_families] == [
            "baseline",
            "primary-source",
            "expert-analysis",
        ]
        assert collector.multi_calls[0][0] == [
            "market structure",
            "market structure official guidance",
            "market structure expert analysis",
        ]
        assert fixtures["expander"].calls[0]["strategy"]["intent"] == "informational"
        assert session.sources[0].query_provenance[0].family == "baseline"
        assert session.metadata["analysis"]["source_provenance"]["families"] == [
            "baseline",
            "primary-source",
            "expert-analysis",
        ]

    @pytest.mark.asyncio
    async def test_duplicate_urls_preserve_multiple_query_families_in_session_metadata(self) -> None:
        """Duplicate URLs should retain provenance from all contributing query families."""
        config = Config()
        config.search.providers = ["tavily"]
        config.search_team.parallel_execution = False

        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))
        shared = SearchResultItem(
            url="https://example.com/shared",
            title="Shared",
            score=0.8,
        )
        collector = FakeCollectorAgent(
            available=["tavily"],
            warnings=[],
            results_by_query={
                "market structure": [shared],
                "market structure official guidance": [
                    SearchResultItem(
                        url="https://example.com/shared",
                        title="Shared better",
                        score=0.95,
                    )
                ],
                "market structure expert analysis": [
                    SearchResultItem(
                        url="https://example.com/expert",
                        title="Expert",
                        score=0.7,
                    )
                ],
            },
        )
        _install_fake_team(orchestrator, collector=collector)

        session = await orchestrator.execute_research(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            min_sources=2,
        )

        shared_source = next(
            source for source in session.sources if source.url == "https://example.com/shared"
        )
        assert [entry.family for entry in shared_source.query_provenance] == [
            "primary-source",
            "baseline",
        ]
        assert session.metadata["analysis"]["source_provenance"]["multi_query_sources"] == 1
        assert session.metadata["analysis"]["source_provenance"]["family_counts"] == {
            "baseline": 1,
            "primary-source": 1,
            "expert-analysis": 1,
        }

    @pytest.mark.asyncio
    async def test_execute_research_records_missing_provider_contract(self) -> None:
        config = Config()
        config.search.providers = ["tavily", "claude"]

        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))
        collector = FakeCollectorAgent(
            available=[],
            warnings=[
                "Provider 'tavily' is configured but unavailable.",
                "Provider 'claude' is selected but no Claude search provider is implemented yet.",
            ],
            results_by_query={
                "market structure": [],
                "market structure official guidance": [],
                "market structure expert analysis": [],
            },
        )
        _install_fake_team(orchestrator, collector=collector)

        session = await orchestrator.execute_research(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            min_sources=1,
        )

        assert session.sources == []
        assert session.metadata["providers"]["configured"] == ["tavily", "claude"]
        assert session.metadata["providers"]["available"] == []
        assert session.metadata["providers"]["status"] == "unavailable"
        assert session.metadata["execution"]["degraded"] is True
        assert session.metadata["execution"]["degraded_reasons"] == [
            "Provider 'tavily' is configured but unavailable.",
            "Provider 'claude' is selected but no Claude search provider is implemented yet.",
        ]

    @pytest.mark.asyncio
    async def test_parallel_failure_falls_back_to_sequential_contract(self) -> None:
        config = Config()
        config.search.providers = ["tavily"]

        orchestrator = TeamResearchOrchestrator(
            config,
            ResearchMonitor(enabled=False),
            parallel_mode=True,
        )
        orchestrator._agent_pool = object()
        orchestrator._monitor.set_session = MagicMock()
        orchestrator._initialize_team = AsyncMock()
        orchestrator._shutdown_team = AsyncMock()
        orchestrator._phase_analyze_strategy = AsyncMock(
            return_value=_make_strategy("parallel query", ResearchDepth.STANDARD, 1)
        )
        orchestrator._phase_expand_queries = AsyncMock(return_value=["parallel query"])
        orchestrator._phase_parallel_research = AsyncMock(side_effect=RuntimeError("parallel boom"))

        sources = _make_sources("fallback", 2)

        async def collect_sources(
            query_families: list[QueryFamily],
            _depth: ResearchDepth,
            _min_sources: int | None,
        ) -> list[SearchResultItem]:
            assert [family.query for family in query_families] == ["parallel query"]
            orchestrator._set_provider_metadata(available=["tavily"], warnings=[])
            return sources

        orchestrator._phase_collect_sources = AsyncMock(side_effect=collect_sources)
        orchestrator._run_analysis_workflow = AsyncMock(
            return_value=(
                _make_analysis(source_count=len(sources)),
                _make_validation(),
                sources,
                [IterationHistoryRecord(iteration=1, source_count=2, quality_score=0.82, gap_count=0)],
            )
        )

        session = await orchestrator.execute_research(
            query="parallel query",
            depth=ResearchDepth.STANDARD,
            min_sources=2,
        )

        assert session.metadata["providers"]["status"] == "ready"
        assert session.metadata["execution"]["parallel_requested"] is True
        assert session.metadata["execution"]["parallel_used"] is False
        assert session.metadata["execution"]["degraded"] is True
        assert session.metadata["execution"]["degraded_reasons"] == [
            "Parallel source collection fell back to sequential mode: parallel boom"
        ]
        orchestrator._phase_collect_sources.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_research_uses_sequential_collection_when_parallel_disabled(self) -> None:
        config = Config()
        config.search.providers = ["tavily"]
        config.search_team.parallel_execution = False

        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))
        orchestrator._monitor.set_session = MagicMock()
        orchestrator._initialize_team = AsyncMock()
        orchestrator._shutdown_team = AsyncMock()
        orchestrator._phase_analyze_strategy = AsyncMock(
            return_value=_make_strategy("sequential query", ResearchDepth.STANDARD, 1)
        )
        orchestrator._phase_expand_queries = AsyncMock(return_value=["sequential query"])
        orchestrator._phase_parallel_research = AsyncMock()

        sources = _make_sources("sequential", 2)

        async def collect_sources(
            query_families: list[QueryFamily],
            _depth: ResearchDepth,
            _min_sources: int | None,
        ) -> list[SearchResultItem]:
            assert [family.query for family in query_families] == ["sequential query"]
            orchestrator._set_provider_metadata(available=["tavily"], warnings=[])
            return sources

        orchestrator._phase_collect_sources = AsyncMock(side_effect=collect_sources)
        orchestrator._run_analysis_workflow = AsyncMock(
            return_value=(
                _make_analysis(source_count=len(sources)),
                _make_validation(),
                sources,
                [IterationHistoryRecord(iteration=1, source_count=2, quality_score=0.82, gap_count=0)],
            )
        )

        session = await orchestrator.execute_research(
            query="sequential query",
            depth=ResearchDepth.STANDARD,
            min_sources=2,
        )

        assert session.metadata["providers"]["status"] == "ready"
        assert session.metadata["execution"]["parallel_requested"] is False
        assert session.metadata["execution"]["parallel_used"] is False
        orchestrator._phase_collect_sources.assert_awaited_once()
        orchestrator._phase_parallel_research.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_workflow_stops_when_validation_needs_no_follow_up(self) -> None:
        config = Config()
        config.research.max_iterations = 3
        config.research.enable_iterative_search = True

        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))
        sources = _make_sources("initial", 2)
        analysis = _make_analysis(source_count=2)
        validation = _make_validation(needs_follow_up=False)

        orchestrator._run_single_analysis_pass = AsyncMock(return_value=(analysis, validation))
        orchestrator._run_follow_up_collection = AsyncMock()

        final_analysis, final_validation, final_sources, history = await orchestrator._run_analysis_workflow(
            query="supply chain",
            depth=ResearchDepth.STANDARD,
            strategy=_make_strategy("supply chain", ResearchDepth.STANDARD, 2),
            sources=sources,
            min_sources=2,
            phase_hook=None,
        )

        assert final_analysis == analysis
        assert final_validation == validation
        assert final_sources == sources
        assert len(history) == 1
        assert orchestrator._run_follow_up_collection.await_count == 0
        assert orchestrator._run_single_analysis_pass.await_count == 1

    @pytest.mark.asyncio
    async def test_workflow_stops_when_follow_up_finds_no_new_sources(self) -> None:
        config = Config()
        config.research.max_iterations = 3
        config.research.enable_iterative_search = True

        orchestrator = TeamResearchOrchestrator(config, ResearchMonitor(enabled=False))
        sources = _make_sources("initial", 2)
        analysis = _make_analysis(source_count=2)
        validation = _make_validation(
            needs_follow_up=True,
            follow_up_queries=["supply chain resilience"],
        )

        orchestrator._run_single_analysis_pass = AsyncMock(return_value=(analysis, validation))
        orchestrator._run_follow_up_collection = AsyncMock(return_value=list(sources))

        final_analysis, final_validation, final_sources, history = await orchestrator._run_analysis_workflow(
            query="supply chain",
            depth=ResearchDepth.STANDARD,
            strategy=_make_strategy("supply chain", ResearchDepth.STANDARD, 2),
            sources=sources,
            min_sources=2,
            phase_hook=None,
        )

        assert final_analysis == analysis
        assert final_validation == validation
        assert final_sources == sources
        assert len(history) == 1
        assert history[0].follow_up_queries == ["supply chain resilience"]
        assert orchestrator._run_follow_up_collection.await_count == 1
        assert orchestrator._run_single_analysis_pass.await_count == 1

    def test_follow_up_queries_are_deduplicated_from_validation_results(self) -> None:
        orchestrator = TeamResearchOrchestrator(Config(), ResearchMonitor(enabled=False))

        analysis = _make_analysis(source_count=1)
        validation = _make_validation(
            needs_follow_up=True,
            follow_up_queries=[
                " query regulation ",
                "Query Regulation",
                "query expert review",
                "query expert review  ",
            ],
        )

        follow_up_queries = orchestrator._get_follow_up_queries(
            "query",
            analysis,
            validation,
        )

        assert follow_up_queries == ["query regulation", "query expert review"]

    def test_follow_up_queries_fall_back_to_gap_suggestions_and_cap_size(self) -> None:
        orchestrator = TeamResearchOrchestrator(Config(), ResearchMonitor(enabled=False))

        analysis = _make_analysis(
            source_count=1,
            gaps=[
                AnalysisGap(
                    gap_description="missing regulatory context",
                    suggested_queries=["query regulation", "query regulation", "query filings"],
                ),
                AnalysisGap(
                    gap_description="missing expert commentary",
                    suggested_queries=[
                        "query interviews",
                        "query testimony",
                        "query responses",
                        "query timeline",
                        "query case studies",
                        "query market reaction",
                        "query analyst notes",
                    ],
                ),
            ],
        )

        follow_up_queries = orchestrator._get_follow_up_queries(
            "query",
            analysis,
            None,
        )

        assert follow_up_queries == [
            "query regulation",
            "query filings",
            "query missing regulatory context",
            "query interviews",
            "query testimony",
            "query responses",
            "query timeline",
            "query case studies",
        ]

    def test_follow_up_queries_can_be_derived_from_validation_failure_modes(self) -> None:
        orchestrator = TeamResearchOrchestrator(Config(), ResearchMonitor(enabled=False))

        analysis = _make_analysis(source_count=3)
        validation = _make_validation(
            needs_follow_up=True,
            failure_modes=[
                "weak_primary_source_coverage",
                "high_contradiction_pressure",
            ],
            evidence_diagnosis="needs_better_sources",
        )

        follow_up_queries = orchestrator._get_follow_up_queries(
            "query",
            analysis,
            validation,
        )

        assert follow_up_queries == [
            "query primary sources official filings",
            "query official guidance source documents",
            "query conflicting evidence rebuttal",
            "query methodology criticism response",
        ]


class TestQueryExpanderAgent:
    """Behavior tests for family-based query expansion."""

    def test_time_sensitive_queries_include_current_updates_family(self) -> None:
        agent = QueryExpanderAgent({})

        families = agent.expand_query(
            "Latest FDA guidance on GLP-1 compounding",
            ResearchDepth.DEEP,
            strategy={
                "intent": "time-sensitive",
                "time_sensitive": True,
                "key_terms": ["fda", "guidance", "compounding"],
                "target_source_classes": ["news", "official_docs"],
            },
        )

        assert any(family.family == "current-updates" for family in families)
        current_updates = next(family for family in families if family.family == "current-updates")
        assert "freshness" in current_updates.intent_tags
        assert "latest" in current_updates.query.lower()

    def test_comparative_queries_include_contrast_oriented_family(self) -> None:
        agent = QueryExpanderAgent({})

        families = agent.expand_query(
            "Compare Nvidia versus AMD data center strategy",
            ResearchDepth.DEEP,
            strategy={
                "intent": "comparative",
                "time_sensitive": False,
                "key_terms": ["nvidia", "amd", "strategy"],
                "target_source_classes": ["official_docs", "market_analysis"],
            },
        )

        contrast_family = next(family for family in families if family.family == "opposing-view")
        assert "contrast" in contrast_family.intent_tags
        assert "tradeoffs" in contrast_family.query.lower()

    def test_deduplicates_semantically_repetitive_variants(self) -> None:
        agent = QueryExpanderAgent({})

        deduplicated = agent._deduplicate_families(
            [
                QueryFamily(query="market structure latest updates", family="current-updates"),
                QueryFamily(query="market structure current developments", family="expert-analysis"),
                QueryFamily(query="market structure official guidance", family="primary-source"),
            ]
        )

        assert len(deduplicated) == 2
        assert [family.family for family in deduplicated] == [
            "current-updates",
            "primary-source",
        ]


class TestOrchestratorError:
    """Tests for orchestrator exceptions."""

    def test_team_execution_error(self) -> None:
        with pytest.raises(TeamExecutionError) as exc_info:
            raise TeamExecutionError(
                message="Test error",
                query="test query",
            )

        error = exc_info.value
        assert str(error) == "Test error"
        assert error.query == "test query"
