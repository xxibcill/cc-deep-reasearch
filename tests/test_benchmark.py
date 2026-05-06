"""Tests for benchmark corpus loading and benchmark infrastructure."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cc_deep_research.benchmark import (
    BenchmarkCase,
    BenchmarkCaseMetrics,
    BenchmarkCaseReport,
    BenchmarkCorpus,
    BenchmarkGateThresholds,
    BenchmarkRunReport,
    BenchmarkScorecard,
    build_benchmark_scorecard,
    default_benchmark_corpus_path,
    evaluate_benchmark_gate,
    get_ready_cases,
    is_release_eligible,
    load_benchmark_corpus,
    run_benchmark_corpus_sync,
    validate_benchmark_corpus,
)
from cc_deep_research.models import ResearchSession, SearchResultItem
from cc_deep_research.models.search import SourceType


def test_load_benchmark_corpus_uses_repo_default() -> None:
    """The default corpus file should load as a valid typed object."""
    corpus = load_benchmark_corpus()

    assert corpus.version == "1.1"
    assert len(corpus.cases) >= 5
    assert any(case.date_sensitive for case in corpus.cases)
    assert {case.category for case in corpus.cases} == {
        "simple_factual",
        "comparison",
        "time_sensitive",
        "evidence_heavy_science_health",
        "market_policy",
    }
    assert all(case.rationale for case in corpus.cases)


def test_default_benchmark_corpus_path_points_to_docs_file() -> None:
    """The repo default path should point at the versioned JSON corpus."""
    path = default_benchmark_corpus_path()

    assert path == Path(__file__).resolve().parents[1] / "docs" / "benchmark_corpus.json"
    assert path.is_file()


def test_benchmark_corpus_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    """Duplicate case IDs should fail validation."""
    payload = {
        "version": "1.0",
        "description": "test",
        "cases": [
            {
                "case_id": "duplicate",
                "query": "one",
                "category": "simple_factual",
                "rationale": "first",
            },
            {
                "case_id": "duplicate",
                "query": "two",
                "category": "comparison",
                "rationale": "second",
            },
        ],
    }
    path = tmp_path / "benchmark_corpus.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate benchmark case ids"):
        load_benchmark_corpus(path)


def test_benchmark_corpus_model_can_validate_loaded_json() -> None:
    """The raw JSON file should round-trip through the schema."""
    path = default_benchmark_corpus_path()
    payload = json.loads(path.read_text(encoding="utf-8"))

    corpus = BenchmarkCorpus.model_validate(payload)

    assert corpus.model_dump(mode="json")["version"] == "1.1"


def test_run_benchmark_corpus_sync_writes_diffable_outputs(tmp_path: Path) -> None:
    """The harness should persist manifest, scorecard, and per-case outputs."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test corpus",
        cases=[
            {
                "case_id": "case-a",
                "query": "first query",
                "category": "simple_factual",
                "rationale": "first rationale",
            },
            {
                "case_id": "case-b",
                "query": "second query",
                "category": "time_sensitive",
                "rationale": "second rationale",
                "date_sensitive": True,
            },
        ],
    )

    async def _run_case(case: object) -> ResearchSession:
        benchmark_case = case
        return ResearchSession(
            session_id=f"session-{benchmark_case.case_id}",
            query=benchmark_case.query,
            started_at=datetime(2026, 3, 7, tzinfo=UTC),
            completed_at=datetime(2026, 3, 7, tzinfo=UTC) + timedelta(seconds=1),
            sources=[
                SearchResultItem(
                    url=f"https://www.example.com/{benchmark_case.case_id}",
                    title="Example",
                    score=0.9,
                    source_metadata={"source_type": "news"},
                )
            ],
            metadata={
                "stop_reason": "success",
                "validation": {"quality_score": 0.8, "issues": [], "failure_modes": []},
                "iteration_history": [{"iteration": 1}],
            },
        )

    report = run_benchmark_corpus_sync(
        corpus,
        run_case=_run_case,
        output_dir=tmp_path,
        configuration={"depth": "standard"},
        generated_at="2026-03-07T00:00:00+00:00",
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    scorecard = json.loads((tmp_path / "scorecard.json").read_text(encoding="utf-8"))
    case_report = json.loads((tmp_path / "cases" / "case-a.json").read_text(encoding="utf-8"))

    assert report.scorecard.total_cases == 2
    assert manifest["generated_at"] == "2026-03-07T00:00:00+00:00"
    assert scorecard["date_sensitive_cases"] == 1
    assert case_report["metrics"]["source_count"] == 1
    assert case_report["source_types"] == ["news"]


def test_build_benchmark_scorecard_aggregates_metrics_deterministically() -> None:
    """Aggregate metrics should be stable for fixed input reports."""
    report = BenchmarkCorpus(
        version="1.0",
        description="scorecard",
        cases=[
            {
                "case_id": "case-a",
                "query": "one",
                "category": "simple_factual",
                "rationale": "rationale",
            }
        ],
    )

    async def _run_case(_: object) -> ResearchSession:
        return ResearchSession(
            session_id="session-1",
            query="one",
            started_at=datetime(2026, 3, 7, tzinfo=UTC),
            completed_at=datetime(2026, 3, 7, tzinfo=UTC) + timedelta(seconds=1.25),
            sources=[
                SearchResultItem(
                    url="https://agency.gov/policy",
                    title="Policy",
                    score=1.0,
                ),
                SearchResultItem(
                    url="https://news.example.com/policy",
                    title="Coverage",
                    score=0.8,
                    source_metadata={"source_type": "news"},
                ),
            ],
            metadata={
                "stop_reason": "limit_reached",
                "validation": {"quality_score": 0.6, "issues": [], "failure_modes": []},
                "iteration_history": [{"iteration": 1}, {"iteration": 2}],
            },
        )

    run_report = run_benchmark_corpus_sync(
        report,
        run_case=_run_case,
        configuration={"depth": "deep"},
        generated_at="2026-03-07T00:00:00+00:00",
    )
    scorecard = build_benchmark_scorecard(run_report.cases)

    assert scorecard.average_source_count == 2.0
    assert scorecard.average_unique_domains == 2.0
    assert scorecard.average_source_type_diversity == 2.0
    assert scorecard.average_latency_ms == 1250.0
    assert scorecard.average_validation_score == 0.6
    assert scorecard.stop_reasons == {"success": 1}


def test_benchmark_source_type_uses_model_field_before_domain_fallback() -> None:
    """Benchmark diversity should honor provider-populated source quality metadata."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="source type",
        cases=[
            {
                "case_id": "case-a",
                "query": "one",
                "category": "simple_factual",
                "rationale": "rationale",
            }
        ],
    )

    async def _run_case(_: object) -> ResearchSession:
        return ResearchSession(
            session_id="session-1",
            query="one",
            started_at=datetime(2026, 3, 7, tzinfo=UTC),
            completed_at=datetime(2026, 3, 7, tzinfo=UTC) + timedelta(seconds=1),
            sources=[
                SearchResultItem(
                    url="https://example.com/report",
                    title="Official report",
                    score=1.0,
                    source_type=SourceType.GOVERNMENT,
                )
            ],
            metadata={"stop_reason": "success"},
        )

    run_report = run_benchmark_corpus_sync(corpus, run_case=_run_case)

    assert run_report.cases[0].source_types == ["government"]


def test_get_ready_cases_filters_non_ready() -> None:
    """Only ready cases should be returned by get_ready_cases."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test",
        cases=[
            BenchmarkCase(case_id="a", query="q", category="simple_factual", rationale="r", status="ready"),
            BenchmarkCase(case_id="b", query="q", category="simple_factual", rationale="r", status="deprecated"),
            BenchmarkCase(case_id="c", query="q", category="simple_factual", rationale="r", status="flaky"),
            BenchmarkCase(case_id="d", query="q", category="simple_factual", rationale="r", status="blocked"),
            BenchmarkCase(case_id="e", query="q", category="simple_factual", rationale="r", status="under_review"),
        ],
    )

    ready = get_ready_cases(corpus)
    # get_ready_cases returns only 'ready' status; use is_release_eligible for broader filter
    assert [c.case_id for c in ready] == ["a"]


def test_is_release_eligible_returns_true_for_ready_and_under_review() -> None:
    """Cases that are ready or under_review should be release eligible."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test",
        cases=[
            BenchmarkCase(case_id="a", query="q", category="simple_factual", rationale="r", status="ready"),
            BenchmarkCase(case_id="b", query="q", category="simple_factual", rationale="r", status="deprecated"),
            BenchmarkCase(case_id="c", query="q", category="simple_factual", rationale="r", status="flaky"),
            BenchmarkCase(case_id="d", query="q", category="simple_factual", rationale="r", status="blocked"),
            BenchmarkCase(case_id="e", query="q", category="simple_factual", rationale="r", status="under_review"),
        ],
    )
    for case in corpus.cases:
        result = is_release_eligible(case)
        if case.status in {"ready", "under_review"}:
            assert result, f"{case.case_id} should be release eligible"
        else:
            assert not result, f"{case.case_id} should not be release eligible"


def test_validate_benchmark_corpus_returns_empty_for_valid_corpus() -> None:
    """A corpus with valid cases should pass validation."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test",
        cases=[
            BenchmarkCase(case_id="a", query="query", category="simple_factual", rationale="r"),
        ],
    )
    errors = validate_benchmark_corpus(corpus)
    assert errors == {}


def test_validate_benchmark_corpus_catches_deprecated_without_notes() -> None:
    """Deprecated cases missing review_notes should fail validation."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test",
        cases=[
            BenchmarkCase(case_id="a", query="q", category="simple_factual", rationale="r", status="deprecated"),
        ],
    )
    errors = validate_benchmark_corpus(corpus)
    assert "a" in errors
    assert any("review_notes" in msg for msg in errors["a"])


def test_validate_benchmark_corpus_catches_invalid_difficulty() -> None:
    """Invalid difficulty values should fail validation."""
    with pytest.raises(Exception, match="difficulty must be one of"):
        BenchmarkCase(
            case_id="a", query="q", category="simple_factual", rationale="r", difficulty="expert"
        )


def test_evaluate_benchmark_gate_passes_when_metrics_are_good() -> None:
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
    assert result.delta_score == 0.05


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


def test_evaluate_benchmark_gate_warns_on_regression() -> None:
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
    """An overridden regression should still show fail but be marked overridden."""
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


def test_include_case_fn_filters_cases() -> None:
    """run_benchmark_corpus_sync should respect include_case_fn."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test",
        cases=[
            BenchmarkCase(case_id="a", query="q", category="simple_factual", rationale="r"),
            BenchmarkCase(case_id="b", query="q", category="simple_factual", rationale="r"),
        ],
    )

    async def _run_case(case: object) -> ResearchSession:
        return ResearchSession(
            session_id=f"session-{case.case_id}",
            query="q",
            started_at=datetime(2026, 3, 7, tzinfo=UTC),
            completed_at=datetime(2026, 3, 7, tzinfo=UTC) + timedelta(seconds=1),
            sources=[],
            metadata={"stop_reason": "success"},
        )

    report = run_benchmark_corpus_sync(
        corpus,
        run_case=_run_case,
        include_case_fn=lambda c: c.case_id == "a",
    )

    assert len(report.cases) == 1
    assert report.cases[0].case_id == "a"


def test_run_benchmark_corpus_sync_includes_metadata_fields() -> None:
    """Case report should include owner, domain, difficulty, status fields."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test",
        cases=[
            BenchmarkCase(
                case_id="a",
                query="q",
                category="simple_factual",
                rationale="r",
                owner="alice",
                domain="science",
                difficulty="advanced",
                status="under_review",
                expected_capabilities=["multi-step", "reasoning"],
            ),
        ],
    )

    async def _run_case(case: object) -> ResearchSession:
        return ResearchSession(
            session_id="s1",
            query="q",
            started_at=datetime(2026, 3, 7, tzinfo=UTC),
            completed_at=datetime(2026, 3, 7, tzinfo=UTC) + timedelta(seconds=1),
            sources=[],
            metadata={"stop_reason": "success"},
        )

    report = run_benchmark_corpus_sync(corpus, run_case=_run_case)
    case_report = report.cases[0]

    assert case_report.owner == "alice"
    assert case_report.domain == "science"
    assert case_report.difficulty == "advanced"
    assert case_report.status == "under_review"
    assert case_report.expected_capabilities == ["multi-step", "reasoning"]


# --- Helpers ---

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
