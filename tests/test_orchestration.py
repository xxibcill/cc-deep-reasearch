"""Focused tests for extracted orchestration helpers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from cc_deep_research.config import Config
from cc_deep_research.models import (
    AnalysisFinding,
    AnalysisResult,
    QueryFamily,
    ResearchDepth,
    StrategyPlan,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.execution import ResearchExecutionHooks, ResearchExecutionService
from cc_deep_research.orchestration.phases import PhaseRunner
from cc_deep_research.orchestration.planning import ResearchPlanningService
from cc_deep_research.orchestration.session_builder import SessionBuilder


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
        }
        assert session.metadata["execution"]["parallel_requested"] is False
        assert session.started_at == started_at
        assert session.completed_at is not None


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
            parallel_mode=False,
            num_researchers=2,
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
            parallel_mode=False,
            num_researchers=2,
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
            parallel_mode=False,
            num_researchers=2,
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
            parallel_mode=False,
            num_researchers=2,
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
