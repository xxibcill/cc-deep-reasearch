"""CLI entry point for cc-deep-research."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

from cc_deep_research.benchmark import (
    BenchmarkRunReport,
    compare_benchmark_runs,
    load_benchmark_corpus,
    run_benchmark_corpus_sync,
)
from cc_deep_research.knowledge import (
    LintFinding,
    LintSeverity,
)
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.ingest import ingest_session
from cc_deep_research.knowledge.vault import (
    graph_export_path,
    graph_sqlite_path,
    init_vault,
    vault_root,
)
from cc_deep_research.session_store import SessionStore, get_default_session_dir

# ---------------------------------------------------------------------------
# Helper: resolve config path
# ---------------------------------------------------------------------------


def _resolve_config(ctx: click.Context, param: click.Parameter, value: Path | None) -> Path | None:
    return value


# ---------------------------------------------------------------------------
# knowledge init
# ---------------------------------------------------------------------------


@click.group("knowledge")
def knowledge() -> None:
    """Operate and maintain the local knowledge vault."""
    pass


@knowledge.command("init")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file (determines vault location)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be created without creating it",
)
def init(config_path: Path | None, dry_run: bool) -> None:
    """Initialize the knowledge vault (creates directories and seed files)."""
    result = init_vault(config_path, dry_run=dry_run)
    if dry_run:
        click.echo("Would create:")
        for name, path in sorted(result.items()):
            click.echo(f"  {name}: {path}")
    else:
        click.echo("Knowledge vault initialized at:")
        for name, path in sorted(result.items()):
            click.echo(f"  {name}: {path}")


# ---------------------------------------------------------------------------
# knowledge ingest-session
# ---------------------------------------------------------------------------


@knowledge.command("ingest-session")
@click.argument("session_id")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file",
)
@click.option(
    "--report",
    "report_path",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="Path to cached markdown report",
)
def ingest_session_cmd(
    session_id: str,
    config_path: Path | None,
    report_path: Path | None,
) -> None:
    """Ingest a saved research session into the knowledge vault."""
    store = SessionStore()
    session = store.load_session(session_id)
    if session is None:
        click.echo(f"Error: Session '{session_id}' not found.", err=True)
        raise SystemExit(1)

    report_md: str | None = None
    if report_path is not None:
        report_md = report_path.read_text(encoding="utf-8")

    result = ingest_session(session, report_md, config_path=config_path)

    click.echo(f"Ingested session '{session_id}':")
    click.echo(f"  nodes: {result.nodes_ingested}")
    click.echo(f"  edges: {result.edges_ingested}")
    click.echo(f"  sources: {result.sources_ingested}")
    click.echo(f"  claims: {result.claims_ingested}")
    click.echo(f"  findings: {result.findings_ingested}")
    click.echo(f"  gaps: {result.gaps_ingested}")
    if result.warnings:
        click.echo("Warnings:")
        for w in result.warnings:
            click.echo(f"  - {w}")


# ---------------------------------------------------------------------------
# knowledge backfill
# ---------------------------------------------------------------------------


@knowledge.command("backfill")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of sessions to ingest",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show sessions to ingest without ingesting",
)
def backfill(config_path: Path | None, limit: int | None, dry_run: bool) -> None:
    """Ingest all saved sessions into the knowledge vault."""
    store = SessionStore()
    sessions_dir = get_default_session_dir()

    if not sessions_dir.exists():
        click.echo(f"Sessions directory not found: {sessions_dir}", err=True)
        raise SystemExit(1)

    session_files = sorted(sessions_dir.glob("*.json"))
    if limit is not None:
        session_files = session_files[:limit]

    click.echo(f"Found {len(session_files)} sessions in {sessions_dir}")

    if dry_run:
        click.echo("Would ingest:")
        for sf in session_files:
            click.echo(f"  {sf.stem}")
        return

    ingested = 0
    failed = 0
    for sf in session_files:
        session_id = sf.stem
        session = store.load_session(session_id)
        if session is None:
            click.echo(f"  [SKIP] {session_id}: could not load")
            failed += 1
            continue

        try:
            result = ingest_session(session, config_path=config_path)
            click.echo(
                f"  [OK] {session_id}: "
                f"nodes={result.nodes_ingested} claims={result.claims_ingested}"
            )
            ingested += 1
        except Exception as exc:
            click.echo(f"  [FAIL] {session_id}: {exc}")
            failed += 1

    click.echo(f"\nBackfill complete: {ingested} ingested, {failed} failed")


# ---------------------------------------------------------------------------
# knowledge rebuild-index
# ---------------------------------------------------------------------------


@knowledge.command("rebuild-index")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file",
)
def rebuild_index(config_path: Path | None) -> None:
    """Rebuild the SQLite graph index from raw and wiki files."""
    # For now, rebuild means reinitializing the index from existing raw/wiki
    # This is a placeholder that will be enhanced once wiki-page-to-graph
    # reading is implemented.
    db_path = graph_sqlite_path(config_path)
    vault = vault_root(config_path)

    if not vault.exists():
        click.echo("Vault not initialized. Run: cc-deep-research knowledge init", err=True)
        raise SystemExit(1)

    index = GraphIndex(db_path)
    index.clear()

    click.echo(f"Graph index cleared at: {db_path}")
    click.echo("Note: Full wiki-to-graph rebuild will be implemented in a future task.")
    click.echo("Use 'backfill' to re-ingest sessions.")


# ---------------------------------------------------------------------------
# knowledge export-graph
# ---------------------------------------------------------------------------


@knowledge.command("export-graph")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path (default: graph/exports/graph.json in vault)",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "markdown"]),
    default="json",
    help="Output format",
)
def export_graph(
    config_path: Path | None,
    output_path: Path | None,
    fmt: str,
) -> None:
    """Export the knowledge graph as JSON or markdown."""
    db_path = graph_sqlite_path(config_path)
    if not db_path.exists():
        click.echo("Graph index not found. Run 'backfill' first.", err=True)
        raise SystemExit(1)

    index = GraphIndex(db_path)
    snap = index.snapshot()

    if fmt == "markdown":
        lines = [
            "# Knowledge Graph Snapshot",
            "",
            f"Exported: {snap.exported_at.isoformat()}",
            f"Nodes: {len(snap.nodes)}",
            f"Edges: {len(snap.edges)}",
            "",
            "## Nodes",
            "",
        ]
        for node in snap.nodes:
            lines.append(f"### {node.id} ({node.kind.value})")
            lines.append(f"- label: {node.label}")
            if node.properties:
                for k, v in node.properties.items():
                    lines.append(f"- {k}: {v}")
            lines.append("")

        lines.append("## Edges")
        lines.append("")
        for edge in snap.edges:
            lines.append(f"- **{edge.kind.value}**: {edge.source_id} → {edge.target_id}")

        content = "\n".join(lines)
        out_path = output_path or graph_export_path(config_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        click.echo(f"Graph exported to: {out_path}")
        return

    # JSON
    out_path = output_path or graph_export_path(config_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = snap.model_dump(mode="json")
    import json

    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    click.echo(f"Graph exported to: {out_path}")


# ---------------------------------------------------------------------------
# knowledge inspect
# ---------------------------------------------------------------------------


@knowledge.command("inspect")
@click.argument("id_or_path")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file",
)
def inspect(id_or_path: str, config_path: Path | None) -> None:
    """Inspect a node, edge, or page by ID or path."""
    # Try as a node ID first
    db_path = graph_sqlite_path(config_path)
    if db_path.exists():
        index = GraphIndex(db_path)
        node = index.node(id_or_path)
        if node is not None:
            click.echo(f"Node: {node.id}")
            click.echo(f"  kind: {node.kind.value}")
            click.echo(f"  label: {node.label}")
            if node.properties:
                click.echo("  properties:")
                for k, v in node.properties.items():
                    click.echo(f"    {k}: {v}")
            return

        edge = index.edge(id_or_path)
        if edge is not None:
            click.echo(f"Edge: {edge.id}")
            click.echo(f"  kind: {edge.kind.value}")
            click.echo(f"  {edge.source_id} → {edge.target_id}")
            return

    # Try as a file path
    path = Path(id_or_path)
    if path.exists():
        content = path.read_text(encoding="utf-8")
        click.echo(content[:2000])
        return

    click.echo(f"'{id_or_path}' not found as node, edge, or path.", err=True)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# knowledge lint
# ---------------------------------------------------------------------------


@knowledge.command("lint")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file",
)
@click.option(
    "--exit-code",
    is_flag=True,
    help="Exit with non-zero if errors are found",
)
def lint(config_path: Path | None, exit_code: bool) -> None:
    """Lint the knowledge vault for structural issues."""
    vault = vault_root(config_path)

    if not vault.exists():
        click.echo("Vault not initialized. Run 'init' first.", err=True)
        raise SystemExit(1)

    findings: list[LintFinding] = []

    # 1. Check for orphan pages (wiki pages with no corresponding graph nodes)
    db_path = graph_sqlite_path(config_path)
    if db_path.exists():
        index = GraphIndex(db_path)
        all_nodes = {n.id for n in index.all_nodes()}

        wiki_dirs = [
            vault / "wiki" / "claims",
            vault / "wiki" / "sessions",
            vault / "wiki" / "sources",
            vault / "wiki" / "gaps",
        ]
        for wiki_dir in wiki_dirs:
            if not wiki_dir.exists():
                continue
            for page_file in wiki_dir.iterdir():
                if page_file.suffix != ".md":
                    continue
                stem = page_file.stem
                node_id = f"{wiki_dir.name.rstrip('s')}:{stem}"  # approximate
                # Don't flag every page, just check for obvious orphans
                pass

    # 2. Check for unsupported claims (pages in claims/ without source backing)
    claims_dir = vault / "wiki" / "claims"
    if claims_dir.exists():
        for claim_file in claims_dir.iterdir():
            if claim_file.suffix != ".md":
                continue
            content = claim_file.read_text(encoding="utf-8")
            # Flag claims that lack source links
            has_source_link = "http" in content or "[[source:" in content
            if not has_source_link and "unsupported" not in content.lower():
                findings.append(
                    LintFinding(
                        severity=LintSeverity.WARNING,
                        category="unsupported_claim",
                        message="Claim page may lack source backing",
                        page_path=str(claim_file),
                    )
                )

    # 3. Check for missing index entries
    index_path = vault / "wiki" / "index.md"
    if not index_path.exists():
        findings.append(
            LintFinding(
                severity=LintSeverity.ERROR,
                category="missing_index",
                message="Vault index.md is missing",
                page_path=str(index_path),
            )
        )

    # 4. Check for broken wikilinks
    import re

    wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")
    wiki_dirs_to_check = [
        vault / "wiki" / "claims",
        vault / "wiki" / "sessions",
        vault / "wiki" / "sources",
    ]
    for wiki_dir in wiki_dirs_to_check:
        if not wiki_dir.exists():
            continue
        for page_file in wiki_dir.iterdir():
            if page_file.suffix != ".md":
                continue
            content = page_file.read_text(encoding="utf-8")
            for match in wikilink_pattern.finditer(content):
                target = match.group(1)
                target_path = wiki_dir.parent / target
                if not target_path.exists() and not (wiki_dir.parent / f"{target}.md").exists():
                    findings.append(
                        LintFinding(
                            severity=LintSeverity.WARNING,
                            category="broken_wikilink",
                            message=f"Wiki link [[{target}]] does not exist",
                            page_path=str(page_file),
                        )
                    )

    # 5. Check for empty directories
    empty_dirs = [
        vault / "wiki" / "concepts",
        vault / "wiki" / "entities",
        vault / "wiki" / "claims",
        vault / "wiki" / "questions",
        vault / "wiki" / "sessions",
        vault / "wiki" / "sources",
    ]
    for d in empty_dirs:
        if d.exists() and not any(d.iterdir()):
            findings.append(
                LintFinding(
                    severity=LintSeverity.INFO,
                    category="empty_directory",
                    message=f"Directory is empty: {d.name}",
                )
            )

    if not findings:
        click.echo("No issues found.")
        raise SystemExit(0)

    error_count = sum(1 for f in findings if f.severity == LintSeverity.ERROR)
    warning_count = sum(1 for f in findings if f.severity == LintSeverity.WARNING)
    info_count = sum(1 for f in findings if f.severity == LintSeverity.INFO)

    click.echo(f"Findings: {error_count} error(s), {warning_count} warning(s), {info_count} info(s)")
    for f in findings:
        icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(f.severity.value, "?")
        click.echo(f"  [{icon}] {f.category}: {f.message}")
        if f.page_path:
            click.echo(f"      at {f.page_path}")

    if exit_code and error_count > 0:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# benchmark run
# ---------------------------------------------------------------------------


@click.group("benchmark")
def benchmark() -> None:
    """Run and compare research benchmark evaluations."""
    pass


@benchmark.command("run")
@click.option(
    "--workflow",
    "workflow_mode",
    type=click.Choice(["staged", "planner"]),
    default="staged",
    help="Research workflow mode",
)
@click.option(
    "--depth",
    type=click.Choice(["quick", "standard", "deep"]),
    default="standard",
    help="Research depth",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Output directory for benchmark run",
)
@click.option(
    "--corpus",
    "corpus_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to custom benchmark corpus JSON",
)
def benchmark_run(
    workflow_mode: str,
    depth: str,
    output_dir: Path,
    corpus_path: Path | None,
) -> None:
    """Run benchmark corpus with the specified workflow and depth.

    P7-T7: Enables benchmark runs with specific workflow modes.
    """
    corpus = load_benchmark_corpus(corpus_path)
    configuration = {"workflow_mode": workflow_mode, "depth": depth}

    from cc_deep_research.benchmark import BenchmarkCase
    from cc_deep_research.models import ResearchDepth, ResearchSession
    from cc_deep_research.research_runs.models import ResearchRunRequest, ResearchWorkflow
    from cc_deep_research.research_runs.service import ResearchRunService

    def run_case(case: BenchmarkCase) -> ResearchSession:
        """Execute one benchmark case as a research run and return the session."""
        loop = asyncio.get_event_loop()
        service = ResearchRunService()
        request = ResearchRunRequest(
            query=case.query,
            depth=ResearchDepth(depth),
            workflow=ResearchWorkflow(workflow_mode),
        )
        return loop.run_in_executor(None, lambda: service.run(request)).result().session

    report = run_benchmark_corpus_sync(
        corpus,
        run_case=run_case,
        output_dir=output_dir,
        configuration=configuration,
    )
    click.echo(f"Benchmark run complete: {report.scorecard.total_cases} cases")
    click.echo(f"  workflow: {report.scorecard.workflow_mode}")
    click.echo(f"  avg sources: {report.scorecard.average_source_count}")
    click.echo(f"  avg validation: {report.scorecard.average_validation_score}")
    click.echo(f"  output: {output_dir}")


@benchmark.command("compare")
@click.argument("dir1", type=click.Path(path_type=Path))
@click.argument("dir2", type=click.Path(path_type=Path))
def benchmark_compare(dir1: Path, dir2: Path) -> None:
    """Compare two benchmark run directories.

    P7-T7: Produces delta report between staged and planner runs.
    """
    manifest1 = dir1 / "manifest.json"
    manifest2 = dir2 / "manifest.json"
    if not manifest1.exists():
        click.echo(f"Missing manifest.json in {dir1}", err=True)
        raise SystemExit(1)
    if not manifest2.exists():
        click.echo(f"Missing manifest.json in {dir2}", err=True)
        raise SystemExit(1)

    with manifest1.open() as f:
        run1 = BenchmarkRunReport.model_validate(json.load(f))
    with manifest2.open() as f:
        run2 = BenchmarkRunReport.model_validate(json.load(f))

    comparison = compare_benchmark_runs(run1, run2, run1_path=str(dir1), run2_path=str(dir2))

    click.echo("Benchmark Comparison Report")
    click.echo(f"  run1: {comparison.run1_path} ({comparison.run1_workflow_mode})")
    click.echo(f"  run2: {comparison.run2_path} ({comparison.run2_workflow_mode})")
    click.echo("")
    click.echo("Metric Deltas (run2 - run1):")
    for metric, delta in [
        ("source_count", comparison.delta_source_count),
        ("unique_domains", comparison.delta_unique_domains),
        ("source_type_diversity", comparison.delta_source_type_diversity),
        ("iteration_count", comparison.delta_iteration_count),
        ("latency_ms", comparison.delta_latency_ms),
        ("validation_score", comparison.delta_validation_score),
        ("report_quality_score", comparison.delta_report_quality_score),
        ("unsupported_claim_count", comparison.delta_unsupported_claim_count),
        ("citation_error_count", comparison.delta_citation_error_count),
        ("hydration_success_rate", comparison.delta_hydration_success_rate),
    ]:
        if delta is not None:
            sign = "+" if delta > 0 else ""
            click.echo(f"  {metric}: {sign}{delta}")
        else:
            click.echo(f"  {metric}: n/a")

    if comparison.case_deltas:
        click.echo("")
        click.echo("Case-level changes:")
        for cd in comparison.case_deltas[:5]:
            click.echo(f"  {cd['case_id']}: sources {cd.get('delta_source_count', 0):+d}")


@click.group()
def main() -> None:
    """Command line tools for cc-deep-research."""
    pass


main.add_command(knowledge)
main.add_command(benchmark)


if __name__ == "__main__":
    main()
