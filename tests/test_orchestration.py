"""Focused tests for extracted orchestration helpers."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cc_deep_research.config import Config
from cc_deep_research.models import (
    AnalysisFinding,
    AnalysisResult,
    PlannerIterationDecision,
    QueryFamily,
    ResearchDepth,
    ResearchPlan,
    ResearchSubtask,
    SearchResultItem,
    StrategyPlan,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.models.llm import LLMProviderType, LLMTransportType
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.analysis_workflow import AnalysisWorkflow
from cc_deep_research.orchestration.execution import (
    ResearchExecutionHooks,
    ResearchExecutionService,
)
from cc_deep_research.orchestration.phases import PhaseRunner
from cc_deep_research.orchestration.planning import ResearchPlanningService
from cc_deep_research.orchestration.resilience import ParallelCollectionError
from cc_deep_research.orchestration.session_builder import SessionBuilder
from cc_deep_research.orchestration.session_state import OrchestratorSessionState
from cc_deep_research.orchestration.source_collection import SourceCollectionService
from cc_deep_research.orchestration.task_dispatcher import TaskDispatcher
from cc_deep_research.prompts import PromptRegistry


def _make_strategy(query: str, depth: ResearchDepth, query_variations: int) -> StrategyResult:
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


class FakeLeadAgent:
    def analyze_query(self, query: str, depth: ResearchDepth) -> StrategyResult:
        variations = {
            ResearchDepth.QUICK: 1,
            ResearchDepth.STANDARD: 3,
            ResearchDepth.DEEP: 4,
        }[depth]
        return _make_strategy(query, depth, variations)


class FakeExpanderAgent:
    def expand_query(
        self,
        query: str,
        depth: ResearchDepth,
        *,
        max_variations: int,
        strategy: dict[str, object],
    ) -> list[QueryFamily]:
        assert depth == ResearchDepth.STANDARD
        assert strategy["intent"] == "informational"
        return [
            QueryFamily(query=query, family="baseline", intent_tags=["baseline"]),
            QueryFamily(query=f"{query} official", family="primary-source", intent_tags=["evidence"]),
            QueryFamily(query=f"{query} analysis", family="expert-analysis", intent_tags=["analysis"]),
        ][:max_variations]


class TestResearchPlanningService:
    @pytest.mark.asyncio
    async def test_analyze_strategy_logs_and_returns_strategy(self) -> None:
        monitor = ResearchMonitor(enabled=False)
        service = ResearchPlanningService(monitor=monitor)

        strategy = await service.analyze_strategy(
            lead=FakeLeadAgent(),
            query="market structure",
            depth=ResearchDepth.STANDARD,
        )

        assert strategy.query == "market structure"
        assert strategy.strategy.query_variations == 3

    @pytest.mark.asyncio
    async def test_analyze_strategy_emits_planner_and_routing_decisions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monitor = ResearchMonitor(enabled=False)
        service = ResearchPlanningService(monitor=monitor, config=Config())

        llm_plan = SimpleNamespace(
            default_route=SimpleNamespace(
                transport=LLMTransportType.OPENROUTER_API,
                provider=LLMProviderType.OPENROUTER,
                model="openrouter/sonnet",
            ),
            agent_routes={
                "analyzer": SimpleNamespace(
                    transport=LLMTransportType.CEREBRAS_API,
                    provider=LLMProviderType.CEREBRAS,
                    model="cerebras/qwen",
                )
            },
            fallback_order=[
                LLMTransportType.OPENROUTER_API,
                LLMTransportType.CEREBRAS_API,
                LLMTransportType.HEURISTIC,
            ],
        )
        monkeypatch.setattr(
            "cc_deep_research.orchestration.planning.create_llm_plan",
            lambda _config, _strategy: llm_plan,
        )

        await service.analyze_strategy(
            lead=FakeLeadAgent(),
            query="market structure",
            depth=ResearchDepth.STANDARD,
        )

        decision_events = [
            event for event in monitor._telemetry_events if event["event_type"] == "decision.made"
        ]
        assert any(
            event["metadata"]["decision_type"] == "planner_strategy"
            and event["metadata"]["chosen_option"] == "moderate"
            for event in decision_events
        )
        assert any(
            event["metadata"]["decision_type"] == "routing"
            and event["metadata"]["chosen_option"] == "openrouter_api"
            for event in decision_events
        )
        assert any(
            event["metadata"]["decision_type"] == "routing"
            and event["metadata"]["chosen_option"] == "cerebras_api"
            for event in decision_events
        )

    @pytest.mark.asyncio
    async def test_expand_queries_short_circuits_for_single_variation(self) -> None:
        monitor = ResearchMonitor(enabled=False)
        service = ResearchPlanningService(monitor=monitor)
        strategy = _make_strategy("market structure", ResearchDepth.QUICK, 1)

        query_families = await service.expand_queries(
            expander=FakeExpanderAgent(),
            query="market structure",
            strategy=strategy,
            depth=ResearchDepth.QUICK,
        )

        assert [family.query for family in query_families] == ["market structure"]
        assert query_families[0].family == "baseline"

    @pytest.mark.asyncio
    async def test_expand_queries_uses_expander_for_multiple_variations(self) -> None:
        monitor = ResearchMonitor(enabled=False)
        service = ResearchPlanningService(monitor=monitor)
        strategy = _make_strategy("market structure", ResearchDepth.STANDARD, 3)

        query_families = await service.expand_queries(
            expander=FakeExpanderAgent(),
            query="market structure",
            strategy=strategy,
            depth=ResearchDepth.STANDARD,
        )

        assert [family.family for family in query_families] == [
            "baseline",
            "primary-source",
            "expert-analysis",
        ]

    @pytest.mark.asyncio
    async def test_expand_queries_adds_knowledge_suggestions_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class FakeKnowledgePlanningService:
            def retrieve_for_planning(
                self,
                query: str,
                *,
                depth: str | None = None,
                enabled: bool = True,
            ) -> SimpleNamespace:
                assert query == "market structure"
                assert depth == "standard"
                assert enabled is True
                return SimpleNamespace(
                    knowledge_retrieved=True,
                    prior_sessions=[],
                    prior_claims=[],
                    prior_gaps=[],
                    suggested_queries=["market structure open questions"],
                    fresh_claims=[],
                    stale_claims=[],
                    unsupported_claims=[],
                )

        monkeypatch.setattr(
            "cc_deep_research.knowledge.planning_integration.KnowledgePlanningService",
            FakeKnowledgePlanningService,
        )
        config = Config()
        config.research.knowledge_assisted_planning = True
        monitor = ResearchMonitor(enabled=False)
        service = ResearchPlanningService(monitor=monitor, config=config)
        strategy = _make_strategy("market structure", ResearchDepth.STANDARD, 3)

        query_families = await service.expand_queries(
            expander=FakeExpanderAgent(),
            query="market structure",
            strategy=strategy,
            depth=ResearchDepth.STANDARD,
        )

        assert [family.family for family in query_families][-1] == "knowledge-gap"
        assert query_families[-1].query == "market structure open questions"
        assert strategy.strategy.knowledge_influence["knowledge_retrieved"] is True
        assert strategy.strategy.knowledge_influence["suggested_queries_from_knowledge"] == [
            "market structure open questions"
        ]


class TestTaskDispatcherRetryPolicy:
    @pytest.mark.asyncio
    async def test_dispatcher_retries_timeout_once_and_succeeds(self) -> None:
        monitor = ResearchMonitor(enabled=False)
        dispatcher = TaskDispatcher(monitor=monitor)
        attempts = 0

        async def flaky_handler(**_: object) -> dict[str, object]:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError("search timed out")
            return {"sources": [], "findings": [], "result": "ok"}

        dispatcher.register_handler("search", flaky_handler)
        plan = ResearchPlan(
            plan_id="plan-1",
            query="market structure",
            summary="retry test",
            subtasks=[
                ResearchSubtask(
                    id="task-1",
                    title="Collect evidence",
                    description="Collect evidence",
                    task_type="search",
                    max_retries=1,
                )
            ],
            execution_order=[["task-1"]],
        )

        results = await dispatcher.dispatch_plan(plan)

        assert attempts == 2
        assert results["task-1"].success is True
        retry_event = next(
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "decision.made"
            and event["metadata"]["decision_type"] == "retry"
        )
        assert retry_event["metadata"]["chosen_option"] == "retry"
        assert retry_event["metadata"]["inputs"]["attempt"] == 1

    @pytest.mark.asyncio
    async def test_dispatcher_stops_after_retry_limit(self) -> None:
        monitor = ResearchMonitor(enabled=False)
        dispatcher = TaskDispatcher(monitor=monitor)
        attempts = 0

        async def always_fails(**_: object) -> dict[str, object]:
            nonlocal attempts
            attempts += 1
            raise TimeoutError("search timed out")

        dispatcher.register_handler("search", always_fails)
        plan = ResearchPlan(
            plan_id="plan-2",
            query="market structure",
            summary="retry exhaustion test",
            subtasks=[
                ResearchSubtask(
                    id="task-1",
                    title="Collect evidence",
                    description="Collect evidence",
                    task_type="search",
                    max_retries=1,
                )
            ],
            execution_order=[["task-1"]],
        )

        results = await dispatcher.dispatch_plan(plan)

        assert attempts == 2
        assert results["task-1"].success is False
        assert plan.get_subtask("task-1").status == "failed"
        retry_events = [
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "decision.made"
            and event["metadata"]["decision_type"] == "retry"
        ]
        assert retry_events[-1]["metadata"]["chosen_option"] == "stop"
        assert retry_events[-1]["reason_code"] == "retry_exhausted"


def _make_analysis() -> AnalysisResult:
    return AnalysisResult(
        key_findings=[AnalysisFinding(title="Finding", description="Description")],
        themes=["Theme"],
    )


def _make_validation() -> ValidationResult:
    return ValidationResult(
        quality_score=0.81,
        is_valid=True,
        issues=[],
        warnings=[],
        recommendations=[],
        needs_follow_up=False,
        follow_up_queries=[],
        target_source_count=3,
    )


def _make_source(url_suffix: str, *, score: float = 0.9) -> SearchResultItem:
    return SearchResultItem(
        url=f"https://example.com/{url_suffix}",
        title=f"Source {url_suffix}",
        snippet=f"Snippet for {url_suffix}",
        score=score,
    )


def _build_metadata(**_: object) -> dict[str, object]:
    return {"status": "ok"}


class TestPhaseRunner:
    @pytest.mark.asyncio
    async def test_run_phase_emits_hook_and_returns_result(self) -> None:
        monitor = ResearchMonitor(enabled=False)
        runner = PhaseRunner(monitor=monitor)
        hook = MagicMock()

        result = await runner.run_phase(
            phase_hook=hook,
            phase_key="strategy",
            description="Analyzing research strategy",
            operation=AsyncMock(return_value="done"),
        )

        assert result == "done"
        hook.assert_called_once_with("strategy", "Analyzing research strategy")


def test_provider_metadata_change_emits_decision_and_state_change() -> None:
    """Provider availability changes should produce both a decision and a linked state change."""
    monitor = ResearchMonitor(enabled=False)
    state = OrchestratorSessionState(
        configured_providers=["tavily", "serpapi"],
        monitor=monitor,
    )
    state.reset(["tavily", "serpapi"])

    state.set_provider_metadata(
        available=["tavily"],
        warnings=["serpapi unavailable"],
    )

    decision_event = next(
        event for event in monitor._telemetry_events if event["event_type"] == "decision.made"
    )
    state_event = next(
        event for event in monitor._telemetry_events if event["event_type"] == "state.changed"
    )

    assert decision_event["metadata"]["decision_type"] == "provider_state"
    assert decision_event["metadata"]["chosen_option"] == "tavily"
    assert state_event["cause_event_id"] == decision_event["event_id"]

    @pytest.mark.asyncio
    async def test_run_analysis_pass_skips_validation_when_disabled(self) -> None:
        monitor = ResearchMonitor(enabled=False)
        runner = PhaseRunner(monitor=monitor)
        strategy = _make_strategy("market structure", ResearchDepth.STANDARD, 3)
        strategy.strategy.enable_quality_scoring = False

        analyze_findings = AsyncMock(return_value=_make_analysis())
        deep_analyze = AsyncMock()
        validate_research = AsyncMock()
        log_validation_results = MagicMock()

        analysis, validation = await runner.run_analysis_pass(
            phase_hook=None,
            query="market structure",
            depth=ResearchDepth.STANDARD,
            strategy=strategy,
            sources=[],
            analyze_findings=analyze_findings,
            deep_analyze=deep_analyze,
            validate_research=validate_research,
            log_validation_results=log_validation_results,
        )

        assert analysis.key_findings[0].title == "Finding"
        assert validation is None
        deep_analyze.assert_not_awaited()
        validate_research.assert_not_awaited()
        log_validation_results.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_analysis_pass_executes_deep_analysis_and_validation(self) -> None:
        monitor = ResearchMonitor(enabled=False)
        runner = PhaseRunner(monitor=monitor)
        strategy = _make_strategy("market structure", ResearchDepth.DEEP, 4)
        deep_analysis = AnalysisResult(themes=["Deep Theme"], deep_analysis_complete=True)
        validation = _make_validation()

        analysis, validated = await runner.run_analysis_pass(
            phase_hook=None,
            query="market structure",
            depth=ResearchDepth.DEEP,
            strategy=strategy,
            sources=[],
            analyze_findings=AsyncMock(return_value=_make_analysis()),
            deep_analyze=AsyncMock(return_value=deep_analysis),
            validate_research=AsyncMock(return_value=validation),
            log_validation_results=MagicMock(),
        )

        assert "Deep Theme" in analysis.themes
        assert validated == validation

    @pytest.mark.asyncio
    async def test_run_analysis_pass_preserves_base_results_when_deep_analysis_is_partial(
        self,
    ) -> None:
        monitor = ResearchMonitor(enabled=False)
        runner = PhaseRunner(monitor=monitor)
        strategy = _make_strategy("market structure", ResearchDepth.DEEP, 4)
        base_analysis = AnalysisResult(
            key_findings=[AnalysisFinding(title="Base finding", description="Base description")],
            themes=["Base Theme"],
            source_count=2,
            analysis_method="ai_semantic",
        )
        partial_deep_analysis = AnalysisResult(
            deep_analysis_complete=True,
            analysis_method="multi_pass",
            analysis_passes=2,
        )
        validation = _make_validation()

        analysis, validated = await runner.run_analysis_pass(
            phase_hook=None,
            query="market structure",
            depth=ResearchDepth.DEEP,
            strategy=strategy,
            sources=[_make_source("analysis-1"), _make_source("analysis-2")],
            analyze_findings=AsyncMock(return_value=base_analysis),
            deep_analyze=AsyncMock(return_value=partial_deep_analysis),
            validate_research=AsyncMock(return_value=validation),
            log_validation_results=MagicMock(),
        )

        assert analysis.key_findings[0].title == "Base finding"
        assert analysis.themes == ["Base Theme"]
        assert analysis.source_count == 2
        assert analysis.deep_analysis_complete is True
        assert analysis.analysis_method == "multi_pass"
        assert analysis.analysis_passes == 2
        assert validated == validation


class TestSourceCollectionService:
    @pytest.mark.asyncio
    async def test_collect_with_fallback_uses_sequential_after_parallel_collection_error(
        self,
    ) -> None:
        config = Config()
        config.search_team.fallback_to_sequential = True
        monitor = ResearchMonitor(enabled=False)
        session_state = OrchestratorSessionState(configured_providers=["tavily"], monitor=monitor)
        session_state.reset(["tavily"])
        collection = SourceCollectionService(
            config=config,
            monitor=monitor,
            session_state=session_state,
            max_concurrent_sources=2,
        )
        expected = [_make_source("sequential-fallback")]
        collection.parallel_research = AsyncMock(
            side_effect=ParallelCollectionError("parallel collectors returned no usable sources")
        )
        collection.collect_sources = AsyncMock(return_value=expected)

        sources = await collection.collect_with_fallback(
            collector=object(),
            agent_pool=object(),
            query_families=[QueryFamily(query="market structure", family="baseline", intent_tags=["baseline"])],
            depth=ResearchDepth.STANDARD,
            min_sources=3,
            prefer_parallel=True,
        )

        assert sources == expected
        collection.collect_sources.assert_awaited_once()
        assert session_state.execution_degradations == [
            "Parallel source collection fell back to sequential mode: "
            "parallel collectors returned no usable sources"
        ]
        fallback_event = next(
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "decision.made"
            and event["metadata"]["decision_type"] == "collection_fallback"
        )
        assert fallback_event["metadata"]["chosen_option"] == "sequential"
        assert fallback_event["metadata"]["inputs"]["error_type"] == "ParallelCollectionError"

    @pytest.mark.asyncio
    async def test_collect_sources_records_provider_failure_degradation_metadata(self) -> None:
        """Provider failure warnings should flow into stable session degradation metadata."""
        config = Config()
        monitor = ResearchMonitor(enabled=False)
        session_state = OrchestratorSessionState(configured_providers=["tavily"], monitor=monitor)
        session_state.reset(["tavily"])
        collection = SourceCollectionService(
            config=config,
            monitor=monitor,
            session_state=session_state,
            max_concurrent_sources=2,
        )

        class FailureAwareCollector:
            async def initialize_providers(self) -> None:
                return None

            def get_provider_warnings(self) -> list[str]:
                return ["All initialized providers failed for query 'market structure'."]

            def get_available_providers(self) -> list[str]:
                return ["tavily"]

            async def collect_sources(
                self,
                query: str,
                options,
                *,
                query_family: QueryFamily,
            ) -> list[SearchResultItem]:
                del query, options, query_family
                return []

            async def collect_multiple_queries(
                self,
                queries: list[str],
                options,
                *,
                query_families: list[QueryFamily],
            ) -> list[SearchResultItem]:
                del queries, options, query_families
                return []

        sources = await collection.collect_sources(
            collector=FailureAwareCollector(),
            query_families=[
                QueryFamily(query="market structure", family="baseline", intent_tags=["baseline"])
            ],
            depth=ResearchDepth.STANDARD,
        )

        assert sources == []
        assert session_state.provider_metadata["warnings"] == [
            "All initialized providers failed for query 'market structure'."
        ]
        assert session_state.execution_degradations == [
            "All initialized providers failed for query 'market structure'."
        ]


class TestAnalysisWorkflow:
    @pytest.mark.asyncio
    async def test_run_stops_when_follow_up_is_requested_without_queries(self) -> None:
        config = Config()
        config.research.enable_iterative_search = True
        config.research.max_iterations = 3
        monitor = ResearchMonitor(enabled=False)
        workflow = AnalysisWorkflow(config=config, monitor=monitor)
        strategy = _make_strategy("market structure", ResearchDepth.STANDARD, 3)
        analysis = _make_analysis()
        validation = ValidationResult(
            quality_score=0.42,
            is_valid=False,
            issues=["More evidence required"],
            warnings=[],
            recommendations=[],
            needs_follow_up=True,
            follow_up_queries=[],
            target_source_count=3,
        )
        collect_follow_up_sources = AsyncMock()

        final_analysis, final_validation, final_sources, history = await workflow.run(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            strategy=strategy,
            sources=[_make_source("initial-1"), _make_source("initial-2")],
            min_sources=2,
            phase_hook=None,
            cancellation_check=None,
            run_single_pass=AsyncMock(return_value=(analysis, validation)),
            collect_follow_up_sources=collect_follow_up_sources,
            plan_iteration=MagicMock(
                return_value=PlannerIterationDecision(
                    should_continue=True,
                    reason_code="planner_requested_more_evidence",
                    rationale="Need another pass, but no concrete follow-up queries are available.",
                    current_hypothesis="Evidence is still thin.",
                    next_queries=[],
                    confidence=0.21,
                )
            ),
        )

        assert final_analysis == analysis
        assert final_validation == validation
        assert len(final_sources) == 2
        assert len(history) == 1
        assert history[0].follow_up_queries == []
        collect_follow_up_sources.assert_not_awaited()
        stop_event = next(
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "decision.made"
            and event["metadata"]["decision_type"] == "iteration_control"
            and event["reason_code"] == "follow_up_queries_unavailable"
        )
        assert stop_event["metadata"]["chosen_option"] == "stop_iteration"


class TestSessionBuilder:
    def test_build_populates_completed_at_and_metadata(self) -> None:
        builder = SessionBuilder()
        started_at = datetime(2026, 3, 7, tzinfo=UTC)

        session = builder.build(
            session_id="research-123",
            query="market structure",
            depth=ResearchDepth.STANDARD,
            sources=[],
            started_at=started_at,
            strategy=_make_strategy("market structure", ResearchDepth.STANDARD, 3),
            analysis=_make_analysis(),
            validation=_make_validation(),
            iteration_history=[],
            build_metadata=_build_metadata,
        )

        assert session.session_id == "research-123"
        assert set(session.metadata) == {
            "strategy",
            "analysis",
            "validation",
            "iteration_history",
            "providers",
            "execution",
            "deep_analysis",
            "llm_routes",
            "prompts",
        }
        assert session.metadata["execution"]["parallel_requested"] is False
        assert session.started_at == started_at
        assert session.completed_at is not None


def test_session_state_records_prompt_metadata() -> None:
    """Session metadata should preserve effective prompt overrides for auditability."""
    state = OrchestratorSessionState(configured_providers=["tavily"])
    registry = PromptRegistry()
    registry.apply_raw_overrides(
        {
            "analyzer": {
                "prompt_prefix": "Focus on primary-source evidence.",
            }
        }
    )

    state.set_prompt_metadata(registry)

    assert state.prompt_metadata.overrides_applied is True
    assert state.prompt_metadata.effective_overrides == {
        "analyzer": {
            "prompt_prefix": "Focus on primary-source evidence.",
            "system_prompt": None,
        }
    }
    assert "deep_analyzer" in state.prompt_metadata.default_prompts_used


class TestResearchExecutionService:
    @pytest.mark.asyncio
    async def test_execute_runs_flow_and_finalizes_session(self, tmp_path) -> None:
        config = Config()
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        phase_runner = PhaseRunner(monitor=monitor)
        service = ResearchExecutionService(
            config=config,
            monitor=monitor,
            phase_runner=phase_runner,
            session_builder=SessionBuilder(),
            configured_providers=lambda: ["tavily"],
            concurrent_source_collection=False,
            max_concurrent_sources=2,
        )
        strategy = _make_strategy("market structure", ResearchDepth.STANDARD, 3)
        query_families = [
            QueryFamily(query="market structure", family="baseline", intent_tags=["baseline"])
        ]
        analysis = _make_analysis()
        validation = _make_validation()
        sources = []
        hook = MagicMock()

        hooks = ResearchExecutionHooks(
            reset_session_state=MagicMock(),
            initialize_team=AsyncMock(),
            analyze_strategy=AsyncMock(return_value=strategy),
            expand_queries=AsyncMock(return_value=query_families),
            normalize_query_families=MagicMock(return_value=query_families),
            collect_sources=AsyncMock(return_value=sources),
            run_analysis_workflow=AsyncMock(return_value=(analysis, validation, sources, [])),
            build_metadata=MagicMock(
                return_value={
                    "providers": {"configured": []},
                    "execution": {"parallel_requested": False},
                }
            ),
            log_session_summary=MagicMock(),
            shutdown_team=AsyncMock(),
        )

        session = await service.execute(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            min_sources=2,
            phase_hook=hook,
            hooks=hooks,
        )

        assert session.query == "market structure"
        assert session.metadata["providers"]["configured"] == []
        assert session.metadata["execution"]["parallel_requested"] is False
        strategy_checkpoint = monitor.get_checkpoints_by_phase("strategy")[0]
        assert strategy_checkpoint["output_ref"] == {
            "summary": None,
            "strategy_type": None,
        }
        assert hook.call_args_list[-2].args == ("complete", "Research complete")
        assert hook.call_args_list[-1].args == ("cleanup", "Cleaning up team resources")

    @pytest.mark.asyncio
    async def test_execute_always_calls_shutdown(self) -> None:
        config = Config()
        monitor = ResearchMonitor(enabled=False)
        phase_runner = PhaseRunner(monitor=monitor)
        service = ResearchExecutionService(
            config=config,
            monitor=monitor,
            phase_runner=phase_runner,
            session_builder=SessionBuilder(),
            configured_providers=lambda: ["tavily"],
            concurrent_source_collection=False,
            max_concurrent_sources=2,
        )
        shutdown_team = AsyncMock()

        hooks = ResearchExecutionHooks(
            reset_session_state=MagicMock(),
            initialize_team=AsyncMock(side_effect=RuntimeError("boom")),
            analyze_strategy=AsyncMock(),
            expand_queries=AsyncMock(),
            normalize_query_families=MagicMock(),
            collect_sources=AsyncMock(),
            run_analysis_workflow=AsyncMock(),
            build_metadata=MagicMock(),
            log_session_summary=MagicMock(),
            shutdown_team=shutdown_team,
        )

        with pytest.raises(RuntimeError, match="boom"):
            await service.execute(
                query="market structure",
                depth=ResearchDepth.STANDARD,
                min_sources=2,
                phase_hook=None,
                hooks=hooks,
            )

        shutdown_team.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_marks_failed_when_providers_unavailable_and_no_sources(self, tmp_path) -> None:
        config = Config()
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        phase_runner = PhaseRunner(monitor=monitor)
        service = ResearchExecutionService(
            config=config,
            monitor=monitor,
            phase_runner=phase_runner,
            session_builder=SessionBuilder(),
            configured_providers=lambda: ["tavily"],
            concurrent_source_collection=False,
            max_concurrent_sources=2,
        )
        strategy = _make_strategy("market structure", ResearchDepth.STANDARD, 3)
        query_families = [
            QueryFamily(query="market structure", family="baseline", intent_tags=["baseline"])
        ]
        analysis = _make_analysis()
        validation = _make_validation()
        sources: list[SearchResultItem] = []

        hooks = ResearchExecutionHooks(
            reset_session_state=MagicMock(),
            initialize_team=AsyncMock(),
            analyze_strategy=AsyncMock(return_value=strategy),
            expand_queries=AsyncMock(return_value=query_families),
            normalize_query_families=MagicMock(return_value=query_families),
            collect_sources=AsyncMock(return_value=sources),
            run_analysis_workflow=AsyncMock(return_value=(analysis, validation, sources, [])),
            build_metadata=MagicMock(
                return_value={
                    "providers": {
                        "configured": ["tavily"],
                        "available": [],
                        "warnings": ["Provider 'tavily' API rate limit exceeded"],
                    },
                    "execution": {
                        "parallel_requested": False,
                        "degraded": True,
                        "degraded_reasons": ["Provider 'tavily' API rate limit exceeded"],
                    },
                }
            ),
            log_session_summary=MagicMock(),
            shutdown_team=AsyncMock(),
        )

        await service.execute(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            min_sources=2,
            phase_hook=None,
            hooks=hooks,
        )

        session_finished = [
            event for event in monitor._telemetry_events if event["event_type"] == "session.finished"
        ]
        assert session_finished[-1]["status"] == "failed"
        session_complete = monitor.get_checkpoints_by_phase("session_complete")[0]
        assert session_complete["output_ref"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_execute_marks_failed_when_all_initialized_providers_fail(self, tmp_path) -> None:
        config = Config()
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        phase_runner = PhaseRunner(monitor=monitor)
        service = ResearchExecutionService(
            config=config,
            monitor=monitor,
            phase_runner=phase_runner,
            session_builder=SessionBuilder(),
            configured_providers=lambda: ["tavily"],
            concurrent_source_collection=False,
            max_concurrent_sources=2,
        )
        strategy = _make_strategy("market structure", ResearchDepth.STANDARD, 3)
        query_families = [
            QueryFamily(query="market structure", family="baseline", intent_tags=["baseline"])
        ]
        analysis = _make_analysis()
        validation = _make_validation()
        sources: list[SearchResultItem] = []

        hooks = ResearchExecutionHooks(
            reset_session_state=MagicMock(),
            initialize_team=AsyncMock(),
            analyze_strategy=AsyncMock(return_value=strategy),
            expand_queries=AsyncMock(return_value=query_families),
            normalize_query_families=MagicMock(return_value=query_families),
            collect_sources=AsyncMock(return_value=sources),
            run_analysis_workflow=AsyncMock(return_value=(analysis, validation, sources, [])),
            build_metadata=MagicMock(
                return_value={
                    "providers": {
                        "configured": ["tavily"],
                        "available": ["tavily"],
                        "warnings": [
                            "All initialized providers failed for query 'market structure'. Continuing with an empty result set from: tavily."
                        ],
                    },
                    "execution": {
                        "parallel_requested": False,
                        "degraded": True,
                        "degraded_reasons": [
                            "All initialized providers failed for query 'market structure'. Continuing with an empty result set from: tavily."
                        ],
                    },
                }
            ),
            log_session_summary=MagicMock(),
            shutdown_team=AsyncMock(),
        )

        await service.execute(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            min_sources=2,
            phase_hook=None,
            hooks=hooks,
        )

        session_finished = [
            event for event in monitor._telemetry_events if event["event_type"] == "session.finished"
        ]
        assert session_finished[-1]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_execute_marks_completed_for_empty_but_valid_provider_results(self, tmp_path) -> None:
        config = Config()
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        phase_runner = PhaseRunner(monitor=monitor)
        service = ResearchExecutionService(
            config=config,
            monitor=monitor,
            phase_runner=phase_runner,
            session_builder=SessionBuilder(),
            configured_providers=lambda: ["tavily"],
            concurrent_source_collection=False,
            max_concurrent_sources=2,
        )
        strategy = _make_strategy("market structure", ResearchDepth.STANDARD, 3)
        query_families = [
            QueryFamily(query="market structure", family="baseline", intent_tags=["baseline"])
        ]
        analysis = _make_analysis()
        validation = _make_validation()
        sources: list[SearchResultItem] = []

        hooks = ResearchExecutionHooks(
            reset_session_state=MagicMock(),
            initialize_team=AsyncMock(),
            analyze_strategy=AsyncMock(return_value=strategy),
            expand_queries=AsyncMock(return_value=query_families),
            normalize_query_families=MagicMock(return_value=query_families),
            collect_sources=AsyncMock(return_value=sources),
            run_analysis_workflow=AsyncMock(return_value=(analysis, validation, sources, [])),
            build_metadata=MagicMock(
                return_value={
                    "providers": {
                        "configured": ["tavily"],
                        "available": ["tavily"],
                        "warnings": ["Provider returned an empty but valid result set"],
                    },
                    "execution": {
                        "parallel_requested": False,
                        "degraded": True,
                        "degraded_reasons": ["Provider returned an empty but valid result set"],
                    },
                }
            ),
            log_session_summary=MagicMock(),
            shutdown_team=AsyncMock(),
        )

        session = await service.execute(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            min_sources=2,
            phase_hook=None,
            hooks=hooks,
        )

        assert session.metadata["execution"]["degraded"] is True
        assert session.metadata["providers"]["status"] == "degraded"
        session_finished = [
            event for event in monitor._telemetry_events if event["event_type"] == "session.finished"
        ]
        assert session_finished[-1]["status"] == "completed"
        session_complete = monitor.get_checkpoints_by_phase("session_complete")[0]
        assert session_complete["output_ref"]["status"] == "completed"
