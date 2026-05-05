"""CI-friendly benchmark utilities: subset selection, mock runner, and documentation."""

from __future__ import annotations

from cc_deep_research.benchmark import BenchmarkCase, BenchmarkCorpus, is_release_eligible

CI_SUBSET_CASE_IDS: set[str] = {
    # Representative: one from each category for fast CI feedback
    "simple-capital-australia",  # simple_factual
    "comparison-batteries-lfp-nmc",  # comparison
    "evidence-health-screen-time",  # evidence_heavy_science_health
    # Omit time_sensitive cases (require live recency checks)
    # Omit market_policy (longer running)
    # Omit planner-heavy cases (more expensive)
}


def get_ci_subset(corpus: BenchmarkCorpus) -> BenchmarkCorpus:
    """Return a small representative subset of cases for CI runs.

    The CI subset is selected to be:
    - Fast: avoids time_sensitive and market_policy cases that need more iterations
    - Representative: covers different categories
    - Stable: only uses ready status cases
    """
    ci_cases = [c for c in corpus.cases if c.case_id in CI_SUBSET_CASE_IDS and is_release_eligible(c)]
    return BenchmarkCorpus(
        version=corpus.version,
        description=f"CI subset of {corpus.description}",
        cases=ci_cases,
    )


def get_ci_case_ids() -> set[str]:
    """Return the set of CI subset case IDs. Useful for allowlist validation."""
    return CI_SUBSET_CASE_IDS


def is_ci_subset_case(case: BenchmarkCase) -> bool:
    """Return True if the case is in the CI subset."""
    return case.case_id in CI_SUBSET_CASE_IDS


CI_RUNTIME_EXPECTATIONS = {
    "description": "CI benchmark subset runtime expectations",
    "subset_size": len(CI_SUBSET_CASE_IDS),
    "expected_wall_time_per_case_seconds": 30,  # approximate
    "total_expected_wall_time_seconds": len(CI_SUBSET_CASE_IDS) * 30,
    "requires_live_credentials": False,
    "case_ids": sorted(CI_SUBSET_CASE_IDS),
    "excluded_categories": ["time_sensitive", "market_policy"],
    "artifact_output": "benchmark_runs/{run_id}/manifest.json",
}
