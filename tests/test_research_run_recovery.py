"""Tests for bounded automatic research-run recovery."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cc_deep_research.models import ResearchSession, SearchResultItem
from cc_deep_research.research_runs.models import (
    ResearchOutputFormat,
    ResearchRunRequest,
    ResearchWorkflow,
)
from cc_deep_research.research_runs.recovery import (
    build_alternate_recovery_request,
    is_terminal_failure,
    load_latest_recovery_checkpoint,
    materialize_failure_result,
    safe_failure_reason,
)
from cc_deep_research.research_runs.recovery_reports import RecoveryReportRenderer
from cc_deep_research.research_runs.resume import ResearchResumeSnapshotError
from cc_deep_research.session_store import SessionStore


def test_alternate_request_switches_execution_path_without_mutating_original() -> None:
    request = ResearchRunRequest(
        query="recover provider failure",
        workflow=ResearchWorkflow.STAGED,
        search_providers=["tavily_basic"],
        concurrent_source_collection=True,
        max_concurrent_sources=4,
    )

    alternate = build_alternate_recovery_request(request)

    assert alternate.workflow == ResearchWorkflow.PLANNER
    assert alternate.search_providers == ["tavily_advanced"]
    assert alternate.concurrent_source_collection is False
    assert alternate.max_concurrent_sources == 1
    assert request.workflow == ResearchWorkflow.STAGED
    assert request.search_providers == ["tavily_basic"]
    assert request.concurrent_source_collection is True


def test_terminal_failure_materializes_and_caches_dependency_free_report(
    tmp_path,
) -> None:
    store = SessionStore(tmp_path / "sessions")
    request = ResearchRunRequest(
        query="research that exhausted recovery",
        output_format=ResearchOutputFormat.MARKDOWN,
    )

    result = materialize_failure_result(
        request,
        session_id="failed-recovery-session",
        failure_reasons=["Alternate execution failed (RuntimeError)."],
        session_store=store,
    )

    assert result.session.metadata["execution"]["terminal_status"] == "failed"
    assert result.report.content.startswith("# Recovery report: research that exhausted recovery")
    assert result.report.path is not None and result.report.path.is_file()
    assert store.report_exists(result.session_id)
    assert store.load_report(result.session_id, ResearchOutputFormat.MARKDOWN) == (
        result.report.content
    )
    assert store.load_session(result.session_id) is not None


def test_shared_recovery_renderer_supports_pipeline_and_terminal_failures() -> None:
    """One dependency-free renderer should cover both recovery report paths."""
    session = ResearchSession(session_id="shared-renderer", query="shared rendering")
    renderer = RecoveryReportRenderer()

    pipeline_markdown, pipeline_json = renderer.render(
        ResearchOutputFormat.JSON,
        session=session,
        analysis={},
        warning="Primary reporter failed.",
    )
    terminal_markdown, terminal_json = renderer.render(
        ResearchOutputFormat.JSON,
        session=session,
        analysis={},
        terminal_status="failed",
    )

    assert pipeline_markdown.startswith("# Recovery report: shared rendering")
    assert '"warning": "Primary reporter failed."' in pipeline_json
    assert terminal_markdown.startswith("# Recovery report: shared rendering")
    assert '"terminal_status": "failed"' in terminal_json


def test_terminal_failure_preserves_saved_session_evidence(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions")
    request = ResearchRunRequest(query="research with partial evidence")
    partial_session = ResearchSession(
        session_id="partial-recovery-session",
        query=request.query,
        sources=[
            SearchResultItem(
                url="https://example.com/evidence",
                title="Recovered source",
                snippet="Evidence collected before the provider failed.",
            )
        ],
        metadata={
            "analysis": {
                "key_findings": ["A partial finding survived the interrupted run."],
                "themes": ["recovery"],
                "gaps": ["The synthesis was incomplete."],
            }
        },
    )
    store.save_session(partial_session)

    result = materialize_failure_result(
        request,
        session_id=partial_session.session_id,
        failure_reasons=["Alternate execution failed (RuntimeError)."],
        session_store=store,
    )

    reloaded = store.load_session(partial_session.session_id)
    assert reloaded is not None
    assert [source.url for source in result.session.sources] == ["https://example.com/evidence"]
    assert [source.url for source in reloaded.sources] == ["https://example.com/evidence"]
    assert result.session.metadata["analysis"]["key_findings"] == [
        "A partial finding survived the interrupted run."
    ]
    assert "A partial finding survived the interrupted run." in result.report.content
    assert "https://example.com/evidence" in result.report.content


def test_safe_failure_reason_does_not_expose_provider_error_details() -> None:
    reason = safe_failure_reason(
        "Initial execution",
        RuntimeError("provider response included token secret-value"),
    )

    assert reason == "Initial execution failed (RuntimeError)."
    assert "secret-value" not in reason


def test_zero_source_unavailable_provider_result_is_terminal_failure() -> None:
    result = SimpleNamespace(
        session=ResearchSession(
            session_id="planner-provider-failure",
            query="planner fallback",
            metadata={
                "providers": {"status": "unavailable"},
                "execution": {},
            },
        )
    )

    assert is_terminal_failure(result)  # type: ignore[arg-type]


def test_checkpoint_loader_skips_invalid_and_non_executable_snapshots(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(origin_session_id=None, origin_checkpoint_id=None)

    class FakeResumeStore:
        def load(self, session_id: str, state_ref: str):
            assert session_id == "recover-session"
            if state_ref == "bad.json":
                raise ResearchResumeSnapshotError("checksum mismatch")
            assert state_ref == "safe.json"
            return state

    monkeypatch.setattr(
        "cc_deep_research.research_runs.recovery.query_session_checkpoints",
        lambda *_args, **_kwargs: {
            "checkpoints": [
                {
                    "checkpoint_id": "cp-safe",
                    "resume_safe": True,
                    "state_ref": "safe.json",
                    "metadata": {"execution_resume": True},
                },
                {
                    "checkpoint_id": "cp-display-only",
                    "resume_safe": True,
                    "state_ref": "display.json",
                    "metadata": {},
                },
                {
                    "checkpoint_id": "cp-corrupt",
                    "resume_safe": True,
                    "state_ref": "bad.json",
                    "metadata": {"execution_resume": True},
                },
            ]
        },
    )

    checkpoint = load_latest_recovery_checkpoint(
        "recover-session",
        telemetry_dir=tmp_path,
        resume_store=FakeResumeStore(),  # type: ignore[arg-type]
    )

    assert checkpoint is not None
    assert checkpoint.checkpoint_id == "cp-safe"
    assert checkpoint.state is state
    assert state.origin_session_id == "recover-session"
    assert state.origin_checkpoint_id == "cp-safe"
