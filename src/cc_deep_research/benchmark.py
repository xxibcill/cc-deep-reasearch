"""Benchmark corpus models, loader utilities, and repeatable harness support."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from cc_deep_research.models import ResearchSession, SearchResultItem

BenchmarkCategory = Literal[
    "simple_factual",
    "comparison",
    "time_sensitive",
    "evidence_heavy_science_health",
    "market_policy",
]
BenchmarkSourceType = Literal["government", "academic", "news", "organization", "commercial", "other"]


class BenchmarkCase(BaseModel):
    """One benchmark prompt used for repeatable evaluation."""

    case_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    category: BenchmarkCategory
    rationale: str = Field(..., min_length=1)
    date_sensitive: bool = Field(default=False)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _dedupe_tags(cls, values: list[str]) -> list[str]:
        """Keep tags stable and compact."""
        return list(dict.fromkeys(value for value in values if value))


class BenchmarkCorpus(BaseModel):
    """Versioned benchmark corpus for evaluation scripts."""

    version: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    cases: list[BenchmarkCase] = Field(default_factory=list, min_length=1)

    @field_validator("cases")
    @classmethod
    def _validate_unique_case_ids(cls, cases: list[BenchmarkCase]) -> list[BenchmarkCase]:
        """Reject duplicate case identifiers."""
        case_ids = [case.case_id for case in cases]
        duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
        if duplicates:
            duplicate_list = ", ".join(duplicates)
            raise ValueError(f"duplicate benchmark case ids: {duplicate_list}")
        return cases


class BenchmarkCaseMetrics(BaseModel):
    """Deterministic metrics used by the benchmark scorecard."""

    source_count: int = Field(default=0, ge=0)
    unique_domains: int = Field(default=0, ge=0)
    source_type_diversity: int = Field(default=0, ge=0)
    iteration_count: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    validation_score: float | None = Field(default=None, ge=0.0, le=1.0)


class BenchmarkCaseReport(BaseModel):
    """Diffable benchmark output for one query corpus case."""

    case_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    category: BenchmarkCategory
    rationale: str = Field(..., min_length=1)
    date_sensitive: bool = Field(default=False)
    tags: list[str] = Field(default_factory=list)
    metrics: BenchmarkCaseMetrics = Field(default_factory=BenchmarkCaseMetrics)
    session_id: str | None = None
    configured_depth: str = Field(default="standard")
    stop_reason: str = Field(default="success")
    validation_issues: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    source_domains: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)


class BenchmarkScorecard(BaseModel):
    """Corpus-level aggregate metrics for repeatable comparisons."""

    total_cases: int = Field(default=0, ge=0)
    average_source_count: float = 0.0
    average_unique_domains: float = 0.0
    average_source_type_diversity: float = 0.0
    average_iteration_count: float = 0.0
    average_latency_ms: float = 0.0
    average_validation_score: float | None = None
    date_sensitive_cases: int = Field(default=0, ge=0)
    stop_reasons: dict[str, int] = Field(default_factory=dict)
    categories: dict[str, int] = Field(default_factory=dict)


class BenchmarkRunReport(BaseModel):
    """Structured, diffable output for a full benchmark corpus run."""

    harness_version: str = Field(default="1.0")
    corpus_version: str = Field(..., min_length=1)
    generated_at: str = Field(..., min_length=1)
    configuration: dict[str, Any] = Field(default_factory=dict)
    scorecard: BenchmarkScorecard
    cases: list[BenchmarkCaseReport] = Field(default_factory=list)


def _extract_domain(url: str) -> str:
    """Return a normalized domain for one source URL."""
    netloc = urlparse(url).netloc.strip().lower()
    return netloc.removeprefix("www.")


def _infer_source_type(source: SearchResultItem) -> BenchmarkSourceType:
    """Infer a stable source-type label for scorecard diversity metrics."""
    explicit = str(source.source_metadata.get("source_type", "")).strip().lower()
    if explicit in {"government", "academic", "news", "organization", "commercial", "other"}:
        return explicit  # type: ignore[return-value]

    domain = _extract_domain(source.url)
    if domain.endswith(".gov"):
        return "government"
    if domain.endswith(".edu"):
        return "academic"
    if domain.endswith(".org"):
        return "organization"
    news_markers = ("news", "times", "post", "reuters", "apnews", "bbc", "cnn", "wsj")
    if any(marker in domain for marker in news_markers):
        return "news"
    if domain:
        return "commercial"
    return "other"


def build_benchmark_case_report(
    case: BenchmarkCase,
    session: ResearchSession,
    *,
    configured_depth: str,
) -> BenchmarkCaseReport:
    """Project one research session into a benchmark report row."""
    domains = sorted({_extract_domain(source.url) for source in session.sources if source.url})
    source_types = sorted({_infer_source_type(source) for source in session.sources})
    validation_payload = (
        session.metadata.get("validation", {})
        if isinstance(session.metadata, dict)
        else {}
    )
    metadata = session.metadata if isinstance(session.metadata, dict) else {}
    iteration_history = metadata.get("iteration_history", []) if isinstance(metadata, dict) else []

    return BenchmarkCaseReport(
        case_id=case.case_id,
        query=case.query,
        category=case.category,
        rationale=case.rationale,
        date_sensitive=case.date_sensitive,
        tags=list(case.tags),
        metrics=BenchmarkCaseMetrics(
            source_count=len(session.sources),
            unique_domains=len(domains),
            source_type_diversity=len(source_types),
            iteration_count=len(iteration_history) if isinstance(iteration_history, list) else 0,
            latency_ms=int(round(session.execution_time_seconds * 1000)),
            validation_score=_coerce_validation_score(validation_payload),
        ),
        session_id=session.session_id,
        configured_depth=configured_depth,
        stop_reason=str(metadata.get("stop_reason", "success")),
        validation_issues=_coerce_string_list(validation_payload.get("issues")),
        failure_modes=_coerce_string_list(validation_payload.get("failure_modes")),
        source_domains=domains,
        source_types=source_types,
    )


def _coerce_validation_score(payload: Any) -> float | None:
    """Extract a numeric validation score from a metadata payload."""
    if not isinstance(payload, dict):
        return None
    value = payload.get("quality_score")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_string_list(value: Any) -> list[str]:
    """Return a stable list of strings from loose metadata."""
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def build_benchmark_scorecard(case_reports: list[BenchmarkCaseReport]) -> BenchmarkScorecard:
    """Aggregate deterministic benchmark metrics across all case reports."""
    if not case_reports:
        return BenchmarkScorecard()

    total_cases = len(case_reports)
    validation_scores = [
        report.metrics.validation_score
        for report in case_reports
        if report.metrics.validation_score is not None
    ]
    stop_reasons: dict[str, int] = {}
    categories: dict[str, int] = {}
    for report in case_reports:
        stop_reasons[report.stop_reason] = stop_reasons.get(report.stop_reason, 0) + 1
        categories[report.category] = categories.get(report.category, 0) + 1

    return BenchmarkScorecard(
        total_cases=total_cases,
        average_source_count=round(
            sum(report.metrics.source_count for report in case_reports) / total_cases, 3
        ),
        average_unique_domains=round(
            sum(report.metrics.unique_domains for report in case_reports) / total_cases, 3
        ),
        average_source_type_diversity=round(
            sum(report.metrics.source_type_diversity for report in case_reports) / total_cases, 3
        ),
        average_iteration_count=round(
            sum(report.metrics.iteration_count for report in case_reports) / total_cases, 3
        ),
        average_latency_ms=round(
            sum(report.metrics.latency_ms for report in case_reports) / total_cases, 3
        ),
        average_validation_score=(
            round(sum(validation_scores) / len(validation_scores), 3) if validation_scores else None
        ),
        date_sensitive_cases=sum(1 for report in case_reports if report.date_sensitive),
        stop_reasons=stop_reasons,
        categories=categories,
    )


async def run_benchmark_corpus(
    corpus: BenchmarkCorpus,
    *,
    run_case: Any,
    output_dir: Path | None = None,
    configuration: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> BenchmarkRunReport:
    """Run the full benchmark corpus with an injected case runner."""
    case_reports: list[BenchmarkCaseReport] = []
    run_configuration = dict(configuration or {})
    configured_depth = str(run_configuration.get("depth", "standard"))

    for case in corpus.cases:
        session = await run_case(case)
        case_reports.append(
            build_benchmark_case_report(
                case,
                session,
                configured_depth=configured_depth,
            )
        )

    report = BenchmarkRunReport(
        corpus_version=corpus.version,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        configuration=run_configuration,
        scorecard=build_benchmark_scorecard(case_reports),
        cases=case_reports,
    )
    if output_dir is not None:
        write_benchmark_report(output_dir, report)
    return report


def write_benchmark_report(output_dir: Path, report: BenchmarkRunReport) -> None:
    """Persist a benchmark run into stable, diffable JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = output_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "manifest.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "scorecard.json").write_text(
        json.dumps(report.scorecard.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    for case_report in report.cases:
        (cases_dir / f"{case_report.case_id}.json").write_text(
            json.dumps(case_report.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )


def run_benchmark_corpus_sync(
    corpus: BenchmarkCorpus,
    *,
    run_case: Any,
    output_dir: Path | None = None,
    configuration: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> BenchmarkRunReport:
    """Synchronous wrapper around the async harness for CLI and tests."""
    return asyncio.run(
        run_benchmark_corpus(
            corpus,
            run_case=run_case,
            output_dir=output_dir,
            configuration=configuration,
            generated_at=generated_at,
        )
    )


def default_benchmark_corpus_path() -> Path:
    """Return the repository-local benchmark corpus path."""
    return Path(__file__).resolve().parents[2] / "docs" / "benchmark_corpus.json"


def load_benchmark_corpus(path: Path | None = None) -> BenchmarkCorpus:
    """Load and validate the benchmark corpus JSON file."""
    corpus_path = path or default_benchmark_corpus_path()
    with corpus_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return BenchmarkCorpus.model_validate(payload)
