"""CLI for running full benchmark corpus for release candidates.

Usage:
    cc-deep-research benchmark run [--depth DEPTH] [--output-dir DIR] [--full]
    cc-deep-research benchmark ci-run [--output-dir DIR]

The full-run workflow runs all corpus cases including deprecated/flaky ones
(explicitly excluded from release gates). The ci-run shortcut runs only the
CI subset for fast feedback.

Examples:
    # Run full benchmark (all cases)
    cc-deep-research benchmark run --depth deep --output-dir benchmark_runs/rc-v1

    # Run CI subset only
    cc-deep-research benchmark ci-run --output-dir benchmark_runs/ci

    # Run full benchmark with planner workflow
    cc-deep-research benchmark run --workflow planner --depth standard
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cc_deep_research.benchmark import (
    get_ci_subset,
    load_benchmark_corpus,
    run_benchmark_corpus_sync,
)
from cc_deep_research.models import ResearchDepth, ResearchSession
from cc_deep_research.research_runs.models import ResearchRunRequest, ResearchWorkflow
from cc_deep_research.research_runs.service import ResearchRunService


def run_case_for_cli(case: object) -> ResearchSession:
    """Execute one benchmark case as a research run."""
    service = ResearchRunService()
    request = ResearchRunRequest(
        query=case.query,
        depth=ResearchDepth("standard"),
        workflow=ResearchWorkflow.STAGED,
    )
    return service.run(request).session


def run_ci_for_cli(case: object) -> ResearchSession:
    """Execute one benchmark case as a research run."""
    service = ResearchRunService()
    request = ResearchRunRequest(
        query=case.query,
        depth=ResearchDepth("quick"),
        workflow=ResearchWorkflow.STAGED,
    )
    return service.run(request).session


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark corpus runner for CI and release workflows",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Full run
    run_parser = subparsers.add_parser("run", help="Run the full benchmark corpus")
    run_parser.add_argument(
        "--depth",
        default="standard",
        choices=["quick", "standard", "deep"],
        help="Research depth (default: standard)",
    )
    run_parser.add_argument(
        "--output-dir",
        help="Output directory for benchmark artifacts",
    )
    run_parser.add_argument(
        "--workflow",
        default="staged",
        choices=["staged", "planner"],
        help="Workflow mode (default: staged)",
    )

    # CI run
    ci_parser = subparsers.add_parser("ci-run", help="Run only the CI benchmark subset")
    ci_parser.add_argument(
        "--output-dir",
        help="Output directory for benchmark artifacts",
    )

    args = parser.parse_args()

    if args.command == "run":
        corpus = load_benchmark_corpus()
        output_dir = Path(args.output_dir) if args.output_dir else None
        configuration = {
            "depth": args.depth,
            "workflow": args.workflow,
        }

        print(f"Running full benchmark corpus ({len(corpus.cases)} cases)...")
        report = run_benchmark_corpus_sync(
            corpus,
            run_case=run_case_for_cli,
            output_dir=output_dir,
            configuration=configuration,
        )
        print(f"  Run ID: {output_dir.name if output_dir else 'N/A'}")
        print(f"  Total cases: {report.scorecard.total_cases}")
        print(f"  Avg validation score: {report.scorecard.average_validation_score}")
        print(f"  Avg latency: {report.scorecard.average_latency_ms}ms")
        return 0

    elif args.command == "ci-run":
        full_corpus = load_benchmark_corpus()
        corpus = get_ci_subset(full_corpus)
        output_dir = Path(args.output_dir) if args.output_dir else None

        print(f"Running CI benchmark subset ({len(corpus.cases)} cases)...")
        report = run_benchmark_corpus_sync(
            corpus,
            run_case=run_ci_for_cli,
            output_dir=output_dir,
            configuration={"depth": "quick"},
        )
        print(f"  Run ID: {output_dir.name if output_dir else 'N/A'}")
        print(f"  Total cases: {report.scorecard.total_cases}")
        print(f"  Avg validation score: {report.scorecard.average_validation_score}")
        print(f"  Avg latency: {report.scorecard.average_latency_ms}ms")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
