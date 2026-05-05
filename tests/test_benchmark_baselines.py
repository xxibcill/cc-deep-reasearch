"""Tests for golden baseline lifecycle and baseline-gated evaluation."""

import json
from pathlib import Path

import pytest

from cc_deep_research.benchmark import (
    BenchmarkCaseMetrics,
    BenchmarkCaseReport,
    BenchmarkGateThresholds,
    BenchmarkRunReport,
    BenchmarkScorecard,
    evaluate_benchmark_gate,
)
from cc_deep_research.benchmark_baselines import (
    BaselineMetadata,
    demote_baseline,
    get_baseline,
    get_promoted_baseline,
    list_baselines,
    load_baseline_run,
    promote_to_baseline,
)


def test_baseline_metadata_round_trip(tmp_path: Path) -> None:
    """BaselineMetadata should serialize and deserialize correctly."""
    metadata = BaselineMetadata(
        run_id="run-20260307",
        run_path="/path/to/run",
        owner="alice",
        approved_at="2026-03-07T00:00:00+00:00",
        approval_note="Initial baseline",
        is_promoted=True,
    )

    as_dict = metadata.to_dict()
    restored = BaselineMetadata.from_dict(as_dict)

    assert restored.run_id == metadata.run_id
    assert restored.run_path == metadata.run_path
    assert restored.owner == metadata.owner
    assert restored.approval_note == metadata.approval_note
    assert restored.is_promoted == metadata.is_promoted


def test_promote_and_list_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Promoting a baseline should appear in list_baselines."""
    # Use a temp dir for the baselines file
    baselines_dir = tmp_path / ".benchmark_baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BENCHMARK_BASELINES_DIR", str(tmp_path / ".benchmark_baselines"))

    # Create a fake run directory
    run_dir = tmp_path / "benchmark_runs" / "run-20260307"
    run_dir.mkdir(parents=True)
    manifest = run_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "harness_version": "1.1",
        "corpus_version": "1.0",
        "generated_at": "2026-03-07T00:00:00+00:00",
        "configuration": {},
        "scorecard": {"total_cases": 2, "average_latency_ms": 500.0},
        "cases": [],
    }), encoding="utf-8")

    metadata = promote_to_baseline(
        run_id="run-20260307",
        run_path=str(run_dir),
        owner="alice",
        approval_note="Initial baseline",
    )

    assert metadata.run_id == "run-20260307"
    assert metadata.is_promoted is True

    baselines = list_baselines()
    assert len(baselines) == 1
    assert baselines[0].run_id == "run-20260307"


def test_demote_removes_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Demoting a baseline should remove it from the registry."""
    baselines_dir = tmp_path / ".benchmark_baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BENCHMARK_BASELINES_DIR", str(tmp_path / ".benchmark_baselines"))

    run_dir = tmp_path / "benchmark_runs" / "run-20260307"
    run_dir.mkdir(parents=True)
    manifest = run_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "harness_version": "1.1",
        "corpus_version": "1.0",
        "generated_at": "2026-03-07T00:00:00+00:00",
        "configuration": {},
        "scorecard": {"total_cases": 2, "average_latency_ms": 500.0},
        "cases": [],
    }), encoding="utf-8")

    promote_to_baseline(run_id="run-20260307", run_path=str(run_dir))
    assert len(list_baselines()) == 1

    success = demote_baseline("run-20260307")
    assert success is True
    assert len(list_baselines()) == 0


def test_get_promoted_baseline_returns_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_promoted_baseline should return the currently promoted baseline."""
    baselines_dir = tmp_path / ".benchmark_baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BENCHMARK_BASELINES_DIR", str(tmp_path / ".benchmark_baselines"))

    run_dir = tmp_path / "benchmark_runs" / "run-20260307"
    run_dir.mkdir(parents=True)
    manifest = run_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "harness_version": "1.1",
        "corpus_version": "1.0",
        "generated_at": "2026-03-07T00:00:00+00:00",
        "configuration": {},
        "scorecard": {"total_cases": 2, "average_latency_ms": 500.0},
        "cases": [],
    }), encoding="utf-8")

    promote_to_baseline(run_id="run-20260307", run_path=str(run_dir))
    baseline = get_promoted_baseline()

    assert baseline is not None
    assert baseline.run_id == "run-20260307"
    assert baseline.is_promoted is True


def test_load_baseline_run_loads_full_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_baseline_run should return the full BenchmarkRunReport."""
    baselines_dir = tmp_path / ".benchmark_baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BENCHMARK_BASELINES_DIR", str(tmp_path / ".benchmark_baselines"))

    run_dir = tmp_path / "benchmark_runs" / "run-20260307"
    run_dir.mkdir(parents=True)
    manifest = run_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "harness_version": "1.1",
        "corpus_version": "1.0",
        "generated_at": "2026-03-07T00:00:00+00:00",
        "configuration": {"depth": "standard"},
        "scorecard": {"total_cases": 2, "average_latency_ms": 500.0},
        "cases": [
            {
                "case_id": "case-a",
                "query": "query",
                "category": "simple_factual",
                "rationale": "r",
                "stop_reason": "success",
                "metrics": {"validation_score": 0.8},
            }
        ],
    }), encoding="utf-8")

    promote_to_baseline(run_id="run-20260307", run_path=str(run_dir))
    report = load_baseline_run("run-20260307")

    assert report is not None
    assert report.corpus_version == "1.0"
    assert len(report.cases) == 1
    assert report.cases[0].case_id == "case-a"


def test_get_baseline_returns_none_for_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_baseline should return None for non-existent baselines."""
    baselines_dir = tmp_path / ".benchmark_baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BENCHMARK_BASELINES_DIR", str(tmp_path / ".benchmark_baselines"))

    baseline = get_baseline("nonexistent")
    assert baseline is None


# --- Gate evaluation tests ---

def _make_run_report(
    cases: list[BenchmarkCaseReport], avg_latency_ms: float
) -> BenchmarkRunReport:
    """Build a BenchmarkRunReport for gate tests."""
    total = len(cases)
    validation_scores = [c.metrics.validation_score for c in cases if c.metrics.validation_score is not None]
    scorecard = BenchmarkScorecard(
        total_cases=total,
        average_latency_ms=avg_latency_ms,
        average_validation_score=sum(validation_scores) / len(validation_scores) if validation_scores else None,
        stop_reasons={"success": sum(1 for c in cases if c.stop_reason == "success")},
        categories={"simple_factual": total},
    )
    return BenchmarkRunReport(
        harness_version="1.1",
        corpus_version="1.0",
        generated_at="2026-03-07T00:00:00+00:00",
        configuration={},
        scorecard=scorecard,
        cases=cases,
    )


def _make_case_report(
    case_id: str,
    stop_reason: str,
    validation_score: float,
) -> BenchmarkCaseReport:
    """Build a BenchmarkCaseReport for gate tests."""
    return BenchmarkCaseReport(
        case_id=case_id,
        query="test query",
        category="simple_factual",
        rationale="test rationale",
        stop_reason=stop_reason,
        metrics=BenchmarkCaseMetrics(validation_score=validation_score),
    )


def test_evaluate_benchmark_gate_passes_when_metrics_improve() -> None:
    """A candidate matching or exceeding baseline should pass."""
    baseline = _make_run_report(
        cases=[
            _make_case_report("a", stop_reason="success", validation_score=0.7),
            _make_case_report("b", stop_reason="success", validation_score=0.8),
        ],
        avg_latency_ms=1000.0,
    )
    candidate = _make_run_report(
        cases=[
            _make_case_report("a", stop_reason="success", validation_score=0.75),
            _make_case_report("b", stop_reason="success", validation_score=0.85),
        ],
        avg_latency_ms=1100.0,
    )

    result = evaluate_benchmark_gate(
        baseline, candidate,
        thresholds=BenchmarkGateThresholds(min_pass_rate=1.0),
        baseline_run_id="baseline",
        candidate_run_id="candidate",
    )

    assert result.outcome == "pass"
    assert result.delta_score is not None and result.delta_score > 0


def test_evaluate_benchmark_gate_fails_on_low_pass_rate() -> None:
    """Candidate below min_pass_rate should fail."""
    baseline = _make_run_report(
        cases=[
            _make_case_report("a", stop_reason="success", validation_score=0.7),
            _make_case_report("b", stop_reason="success", validation_score=0.8),
        ],
        avg_latency_ms=1000.0,
    )
    candidate = _make_run_report(
        cases=[
            _make_case_report("a", stop_reason="validation_failed", validation_score=0.1),
            _make_case_report("b", stop_reason="success", validation_score=0.8),
        ],
        avg_latency_ms=1000.0,
    )

    result = evaluate_benchmark_gate(
        baseline, candidate,
        thresholds=BenchmarkGateThresholds(min_pass_rate=0.8),
    )

    assert result.outcome == "fail"
    assert len(result.failing_cases) == 1
    assert result.failing_cases[0]["case_id"] == "a"


def test_evaluate_benchmark_gate_warns_on_score_regression() -> None:
    """A significant validation score drop should warn."""
    baseline = _make_run_report(
        cases=[_make_case_report("a", stop_reason="success", validation_score=0.8)],
        avg_latency_ms=1000.0,
    )
    candidate = _make_run_report(
        cases=[_make_case_report("a", stop_reason="success", validation_score=0.6)],
        avg_latency_ms=1000.0,
    )

    result = evaluate_benchmark_gate(baseline, candidate)

    assert result.outcome == "warning"
    assert len(result.regressions) == 1


def test_evaluate_benchmark_gate_allows_override() -> None:
    """An overridden regression should be marked as overridden."""
    baseline = _make_run_report(
        cases=[_make_case_report("a", stop_reason="success", validation_score=0.8)],
        avg_latency_ms=1000.0,
    )
    candidate = _make_run_report(
        cases=[_make_case_report("a", stop_reason="success", validation_score=0.3)],
        avg_latency_ms=1000.0,
    )

    result = evaluate_benchmark_gate(
        baseline, candidate,
        override_notes="Known regression in experiment",
    )

    assert result.outcome == "fail"
    assert result.overridden is True
    assert result.override_notes == "Known regression in experiment"


def test_evaluate_benchmark_gate_uses_default_thresholds() -> None:
    """Calling without thresholds should use defaults."""
    baseline = _make_run_report(
        cases=[_make_case_report("a", stop_reason="success", validation_score=0.8)],
        avg_latency_ms=1000.0,
    )
    candidate = _make_run_report(
        cases=[_make_case_report("a", stop_reason="success", validation_score=0.8)],
        avg_latency_ms=1000.0,
    )

    result = evaluate_benchmark_gate(baseline, candidate)

    assert result.outcome == "pass"
