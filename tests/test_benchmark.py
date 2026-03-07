"""Tests for benchmark corpus loading."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cc_deep_research.benchmark import (
    BenchmarkCorpus,
    build_benchmark_scorecard,
    default_benchmark_corpus_path,
    load_benchmark_corpus,
    run_benchmark_corpus_sync,
)
from cc_deep_research.models import ResearchSession, SearchResultItem


def test_load_benchmark_corpus_uses_repo_default() -> None:
    """The default corpus file should load as a valid typed object."""
    corpus = load_benchmark_corpus()

    assert corpus.version == "1.0"
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

    assert corpus.model_dump(mode="json")["version"] == "1.0"


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
