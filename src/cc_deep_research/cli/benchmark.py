"""Benchmark command registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from cc_deep_research.benchmark import load_benchmark_corpus, run_benchmark_corpus_sync
from cc_deep_research.config import load_config
from cc_deep_research.monitoring import ResearchMonitor


def register_benchmark_commands(cli: click.Group) -> None:
    """Register benchmark commands."""

    @cli.group()
    def benchmark() -> None:
        """Run the versioned benchmark corpus."""

    @benchmark.command("run")
    @click.option(
        "--corpus-path",
        type=click.Path(path_type=Path, dir_okay=False),
        default=None,
        help="Benchmark corpus JSON path.",
    )
    @click.option(
        "--output-dir",
        type=click.Path(path_type=Path, file_okay=False),
        default=Path("benchmark_runs") / "latest",
        show_default=True,
        help="Directory for structured benchmark outputs.",
    )
    @click.option(
        "--depth",
        type=click.Choice(["quick", "standard", "deep"], case_sensitive=False),
        default="standard",
        show_default=True,
        help="Fixed research depth used for every benchmark case.",
    )
    @click.option(
        "--sources",
        "min_sources",
        type=int,
        default=None,
        help="Optional minimum source override applied to every case.",
    )
    @click.option("--monitor", is_flag=True, help="Enable monitor output during corpus execution.")
    def benchmark_run(
        corpus_path: Path | None,
        output_dir: Path,
        depth: str,
        min_sources: int | None,
        monitor: bool,
    ) -> None:
        """Execute the whole benchmark corpus and persist a diffable report."""
        from cc_deep_research.models import ResearchDepth
        from cc_deep_research.orchestrator import TeamResearchOrchestrator

        corpus = load_benchmark_corpus(corpus_path)
        config = load_config()
        benchmark_monitor = ResearchMonitor(enabled=monitor)
        orchestrator = TeamResearchOrchestrator(config=config, monitor=benchmark_monitor)
        depth_enum = ResearchDepth(depth.lower())

        async def _run_case(case: Any) -> Any:
            return await orchestrator.execute_research(
                query=case.query,
                depth=depth_enum,
                min_sources=min_sources,
            )

        report = run_benchmark_corpus_sync(
            corpus,
            run_case=_run_case,
            output_dir=output_dir,
            configuration={
                "depth": depth_enum.value,
                "min_sources": min_sources,
                "providers": list(config.search.providers),
            },
        )
        click.echo(
            "Benchmark complete: "
            f"{report.scorecard.total_cases} cases, "
            f"avg score={report.scorecard.average_validation_score}, "
            f"output={output_dir}"
        )


__all__ = ["register_benchmark_commands"]
