"""Tests for CI benchmark subset selection and membership stability."""

from cc_deep_research.benchmark import BenchmarkCase, BenchmarkCorpus
from cc_deep_research.benchmark_ci import (
    CI_SUBSET_CASE_IDS,
    get_ci_case_ids,
    get_ci_subset,
    is_ci_subset_case,
)


def test_ci_subset_case_ids_is_stable() -> None:
    """The CI subset should be a frozen set of known case IDs."""
    assert len(CI_SUBSET_CASE_IDS) >= 3
    assert all(isinstance(cid, str) for cid in CI_SUBSET_CASE_IDS)
    # Should not be empty
    assert "simple-capital-australia" in CI_SUBSET_CASE_IDS


def test_get_ci_subset_returns_only_ci_cases() -> None:
    """get_ci_subset should return only cases in the CI subset."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test",
        cases=[
            BenchmarkCase(
                case_id="simple-capital-australia",
                query="q",
                category="simple_factual",
                rationale="r",
            ),
            BenchmarkCase(
                case_id="comparison-batteries-lfp-nmc",
                query="q",
                category="comparison",
                rationale="r",
            ),
            BenchmarkCase(
                case_id="evidence-health-screen-time",
                query="q",
                category="evidence_heavy_science_health",
                rationale="r",
            ),
            BenchmarkCase(
                case_id="time-sensitive-ai-chip-rules",
                query="q",
                category="time_sensitive",
                rationale="r",
            ),
            BenchmarkCase(
                case_id="market-policy-carbon-border",
                query="q",
                category="market_policy",
                rationale="r",
            ),
        ],
    )

    ci = get_ci_subset(corpus)
    ci_ids = {c.case_id for c in ci.cases}

    assert ci_ids.issubset(CI_SUBSET_CASE_IDS)
    assert "time-sensitive-ai-chip-rules" not in ci_ids
    assert "market-policy-carbon-border" not in ci_ids


def test_get_ci_subset_excludes_deprecated_cases() -> None:
    """get_ci_subset should skip deprecated/flaky/blocked cases even if in subset."""
    corpus = BenchmarkCorpus(
        version="1.0",
        description="test",
        cases=[
            BenchmarkCase(
                case_id="simple-capital-australia",
                query="q",
                category="simple_factual",
                rationale="r",
                status="deprecated",
            ),
            BenchmarkCase(
                case_id="comparison-batteries-lfp-nmc",
                query="q",
                category="comparison",
                rationale="r",
            ),
        ],
    )

    ci = get_ci_subset(corpus)
    ci_ids = {c.case_id for c in ci.cases}

    assert "simple-capital-australia" not in ci_ids
    assert "comparison-batteries-lfp-nmc" in ci_ids


def test_is_ci_subset_case() -> None:
    """is_ci_subset_case should return True for CI subset cases."""
    in_ci = BenchmarkCase(
        case_id="simple-capital-australia",
        query="q",
        category="simple_factual",
        rationale="r",
    )
    not_in_ci = BenchmarkCase(
        case_id="time-sensitive-ai-chip-rules",
        query="q",
        category="time_sensitive",
        rationale="r",
    )

    assert is_ci_subset_case(in_ci) is True
    assert is_ci_subset_case(not_in_ci) is False


def test_get_ci_case_ids() -> None:
    """get_ci_case_ids should return the CI subset case IDs as a set."""
    ids = get_ci_case_ids()
    assert ids == CI_SUBSET_CASE_IDS
    assert "simple-capital-australia" in ids
