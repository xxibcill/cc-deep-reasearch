"""Tests for durable research-run resume state."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from cc_deep_research.config import Config
from cc_deep_research.models import (
    AnalysisResult,
    QueryFamily,
    ResearchDepth,
    ResearchPlan,
    ResearchSubtask,
    SearchResultItem,
    StrategyPlan,
    StrategyResult,
    TaskExecutionResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.execution import (
    ResearchExecutionHooks,
    ResearchExecutionService,
)
from cc_deep_research.orchestration.phases import PhaseRunner
from cc_deep_research.orchestration.session_builder import SessionBuilder
from cc_deep_research.orchestration.task_dispatcher import TaskDispatcher
from cc_deep_research.research_runs.models import ResearchRunRequest, ResearchWorkflow
from cc_deep_research.research_runs.resume import (
    ResearchResumePhase,
    ResearchResumeSnapshotError,
    ResearchResumeState,
    ResearchResumeStore,
    build_config_fingerprint,
)


def _state() -> ResearchResumeState:
    return ResearchResumeState(
        workflow=ResearchWorkflow.STAGED,
        query="What changed?",
        depth=ResearchDepth.STANDARD,
        min_sources=4,
        next_phase=ResearchResumePhase.STRATEGY,
        request=ResearchRunRequest(
            query="What changed?",
            depth=ResearchDepth.STANDARD,
            min_sources=4,
        ),
        config_fingerprint=build_config_fingerprint(Config()),
    )


def test_resume_store_round_trips_a_checksummed_snapshot(tmp_path) -> None:
    store = ResearchResumeStore(tmp_path)
    state = _state()

    reference = store.save("session-1", state)
    restored = store.load("session-1", reference.path)

    assert restored == state
    assert reference.path.startswith("resume/")
    assert len(reference.content_hash) == 64


def test_resume_store_rejects_tampered_snapshot(tmp_path) -> None:
    store = ResearchResumeStore(tmp_path)
    reference = store.save("session-1", _state())
    snapshot_path = tmp_path / "session-1" / reference.path
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    payload["state"]["query"] = "tampered"
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResearchResumeSnapshotError, match="checksum"):
        store.load("session-1", reference.path)


def test_resume_store_rejects_path_traversal(tmp_path) -> None:
    store = ResearchResumeStore(tmp_path)

    with pytest.raises(ResearchResumeSnapshotError, match="reference"):
        store.load("session-1", "../../outside.json")


def test_resume_state_rejects_missing_phase_prerequisites() -> None:
    with pytest.raises(ValueError, match="strategy"):
        ResearchResumeState(
            workflow=ResearchWorkflow.STAGED,
            query="What changed?",
            depth=ResearchDepth.STANDARD,
            next_phase=ResearchResumePhase.SOURCE_COLLECTION,
            request=ResearchRunRequest(query="What changed?"),
            config_fingerprint=build_config_fingerprint(Config()),
        )


def test_resume_state_rejects_phase_from_other_workflow() -> None:
    with pytest.raises(ValueError, match="not a staged workflow phase"):
        ResearchResumeState(
            workflow=ResearchWorkflow.STAGED,
            query="What changed?",
            depth=ResearchDepth.STANDARD,
            next_phase=ResearchResumePhase.PLANNER_PLAN,
            request=ResearchRunRequest(query="What changed?"),
            config_fingerprint=build_config_fingerprint(Config()),
        )


def test_config_fingerprint_does_not_change_for_secret_values() -> None:
    first = Config()
    second = Config()

    first_payload = first.model_dump(mode="python")
    second_payload = second.model_dump(mode="python")
    first_payload.setdefault("search", {})["api_key"] = "first-secret"
    second_payload.setdefault("search", {})["api_key"] = "second-secret"

    assert build_config_fingerprint(first_payload) == build_config_fingerprint(second_payload)


def test_config_fingerprint_tracks_non_secret_token_limits() -> None:
    assert build_config_fingerprint({"max_tokens": 1000}) != build_config_fingerprint(
        {"max_tokens": 2000}
    )


def _strategy() -> StrategyResult:
    return StrategyResult(
        query="What changed?",
        complexity="moderate",
        depth=ResearchDepth.STANDARD,
        profile={"intent": "informational"},
        strategy=StrategyPlan(
            query_variations=1,
            max_sources=4,
            tasks=["collect", "analyze"],
        ),
    )


def _hooks(*, analysis_error: Exception | None = None) -> ResearchExecutionHooks:
    strategy = _strategy()
    families = [QueryFamily(query="What changed?", family="baseline")]
    sources = [
        SearchResultItem(
            url="https://example.com/source",
            title="Source",
            content="Durable source content",
        )
    ]
    analysis_result = (
        AsyncMock(side_effect=analysis_error)
        if analysis_error is not None
        else AsyncMock(
            return_value=(
                AnalysisResult(key_findings=["Recovered finding"], source_count=1),
                ValidationResult(is_valid=True, quality_score=0.9),
                sources,
                [],
            )
        )
    )
    return ResearchExecutionHooks(
        reset_session_state=MagicMock(),
        initialize_team=AsyncMock(),
        analyze_strategy=AsyncMock(return_value=strategy),
        expand_queries=AsyncMock(return_value=families),
        normalize_query_families=MagicMock(return_value=families),
        collect_sources=AsyncMock(return_value=sources),
        run_analysis_workflow=analysis_result,
        build_metadata=MagicMock(
            return_value={
                "providers": {"configured": ["test"], "available": ["test"]},
                "execution": {"parallel_requested": False},
            }
        ),
        log_session_summary=MagicMock(),
        shutdown_team=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_staged_resume_reuses_sources_after_analysis_failure(tmp_path) -> None:
    config = Config()
    request = ResearchRunRequest(
        query="What changed?",
        depth=ResearchDepth.STANDARD,
        min_sources=4,
    )
    store = ResearchResumeStore(tmp_path)
    failed_monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    failed_service = ResearchExecutionService(
        config=config,
        monitor=failed_monitor,
        phase_runner=PhaseRunner(monitor=failed_monitor),
        session_builder=SessionBuilder(),
        configured_providers=lambda: ["test"],
        concurrent_source_collection=False,
        max_concurrent_sources=1,
        run_request=request,
        resume_store=store,
        config_fingerprint=build_config_fingerprint(config),
    )

    with pytest.raises(RuntimeError, match="analysis failed"):
        await failed_service.execute(
            query=request.query,
            depth=request.depth,
            min_sources=request.min_sources,
            phase_hook=None,
            hooks=_hooks(analysis_error=RuntimeError("analysis failed")),
        )

    checkpoint = failed_monitor.get_latest_resume_safe_checkpoint()
    assert checkpoint is not None
    assert checkpoint["state_ref"]
    failed_session_id = failed_monitor.session_id
    assert failed_session_id is not None
    resume_state = store.load(failed_session_id, checkpoint["state_ref"])
    assert resume_state.next_phase == ResearchResumePhase.ANALYSIS
    assert resume_state.sources[0].content == "Durable source content"

    resume_monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    resume_service = ResearchExecutionService(
        config=config,
        monitor=resume_monitor,
        phase_runner=PhaseRunner(monitor=resume_monitor),
        session_builder=SessionBuilder(),
        configured_providers=lambda: ["test"],
        concurrent_source_collection=False,
        max_concurrent_sources=1,
        run_request=request,
        resume_store=store,
        config_fingerprint=build_config_fingerprint(config),
    )
    resume_hooks = _hooks()

    session = await resume_service.resume(
        resume_state,
        phase_hook=None,
        hooks=resume_hooks,
    )

    resume_hooks.analyze_strategy.assert_not_awaited()
    resume_hooks.expand_queries.assert_not_awaited()
    resume_hooks.collect_sources.assert_not_awaited()
    resume_hooks.run_analysis_workflow.assert_awaited_once()
    assert session.sources[0].url == "https://example.com/source"
    assert session.metadata["resume"]["original_session_id"] == failed_session_id


@pytest.mark.asyncio
async def test_planner_dispatch_resume_skips_successful_tasks() -> None:
    monitor = ResearchMonitor(enabled=False)
    dispatcher = TaskDispatcher(monitor=monitor)
    calls = {"search": 0, "analyze": 0}

    async def search_handler(**_kwargs):
        calls["search"] += 1
        return {"findings": ["should not run"]}

    async def analyze_handler(**_kwargs):
        calls["analyze"] += 1
        return {"findings": ["continued analysis"]}

    dispatcher.register_handler("search", search_handler)
    dispatcher.register_handler("analyze", analyze_handler)
    plan = ResearchPlan(
        plan_id="plan-resume",
        query="What changed?",
        summary="Resume completed task groups",
        subtasks=[
            ResearchSubtask(
                id="search",
                title="Search",
                description="Collect sources",
                task_type="search",
            ),
            ResearchSubtask(
                id="analyze",
                title="Analyze",
                description="Analyze sources",
                task_type="analyze",
                dependencies=["search"],
            ),
        ],
        execution_order=[["search"], ["analyze"]],
    )
    restored = {
        "search": TaskExecutionResult(
            task_id="search",
            success=True,
            outputs={"findings": ["saved search"]},
            findings=["saved search"],
        )
    }
    snapshots: list[dict[str, TaskExecutionResult]] = []

    async def capture_group(results: dict[str, TaskExecutionResult]) -> None:
        snapshots.append(results)

    results = await dispatcher.dispatch_plan(
        plan,
        initial_results=restored,
        group_completed_callback=capture_group,
    )

    assert calls == {"search": 0, "analyze": 1}
    assert set(results) == {"search", "analyze"}
    assert snapshots[-1]["search"].findings == ["saved search"]
