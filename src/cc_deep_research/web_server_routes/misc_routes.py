"""Search cache, benchmark, theme, and analytics HTTP API routes."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from cc_deep_research.benchmark import (
    BenchmarkGateThresholds,
    BenchmarkRunReport,
    compare_benchmark_runs,
    load_benchmark_corpus,
    run_benchmark_corpus_sync,
)
from cc_deep_research.benchmark_baselines import (
    demote_baseline,
    get_baseline,
    get_promoted_baseline,
    list_baselines,
    load_baseline_run,
    promote_to_baseline,
)
from cc_deep_research.config import load_config
from cc_deep_research.search_cache import SearchCacheStore
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import (
    _load_dashboard_connection,
)
from cc_deep_research.web_server_routes._shared import serialize_timestamp

if TYPE_CHECKING:
    from cc_deep_research.llm.codex_runtime import CodexRuntime


def _get_research_theme_list() -> list[dict[str, str]]:
    """Return list of available research themes with metadata."""
    from cc_deep_research.themes import get_theme_registry

    registry = get_theme_registry()
    theme_info = registry.list_theme_info()

    return [
        {
            "theme": item["theme"],
            "display_name": item["display_name"],
            "description": item["description"],
            "source": item["source"],
        }
        for item in theme_info
    ]


def _run_benchmark_job(
    *,
    workflow_mode: str,
    depth: str,
    output_dir: str,
    codex_runtime: CodexRuntime | None = None,
) -> dict[str, Any]:
    """Run the benchmark corpus inside a background worker thread."""
    from cc_deep_research.benchmark import BenchmarkCase
    from cc_deep_research.models import ResearchDepth, ResearchSession
    from cc_deep_research.research_runs.models import ResearchRunRequest, ResearchWorkflow
    from cc_deep_research.research_runs.service import ResearchRunService

    corpus = load_benchmark_corpus()
    configuration = {"workflow_mode": workflow_mode, "depth": depth}
    run_output_dir = Path(output_dir)

    def run_case(case: BenchmarkCase) -> ResearchSession:
        """Execute one benchmark case as a research run and return the session."""
        service = ResearchRunService(codex_runtime=codex_runtime)
        request = ResearchRunRequest(
            query=case.query,
            depth=ResearchDepth(depth),
            workflow=ResearchWorkflow(workflow_mode),
        )
        return service.run(request).session

    report = run_benchmark_corpus_sync(
        corpus,
        run_case=run_case,
        output_dir=run_output_dir,
        configuration=configuration,
    )
    return {
        "run_id": run_output_dir.name,
        "output_dir": str(run_output_dir),
        "total_cases": report.scorecard.total_cases,
        "workflow_mode": report.scorecard.workflow_mode,
        "average_validation_score": report.scorecard.average_validation_score,
    }


def _query_analytics_data(
    db_path: Path | None = None,
    days_back: int = 30,
) -> dict[str, Any]:
    """Query aggregate analytics data from the telemetry database."""
    from cc_deep_research.telemetry import get_default_dashboard_db_path

    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {
            "summary": {
                "total_runs": 0,
                "completed_runs": 0,
                "failed_runs": 0,
                "interrupted_runs": 0,
                "avg_duration_ms": 0,
                "avg_sources": 0,
                "report_availability_rate": 0,
            },
            "status_counts": [],
            "duration_by_status": [],
            "sources_trend": [],
            "daily_volume": [],
            "depth_distribution": [],
        }

    conn = _load_dashboard_connection(database_path)

    summary = conn.execute(
        """
        SELECT
            COUNT(*) AS total_runs,
            SUM(CASE WHEN status IN ('completed', 'success') THEN 1 ELSE 0 END) AS completed_runs,
            SUM(CASE WHEN status IN ('failed', 'error') THEN 1 ELSE 0 END) AS failed_runs,
            SUM(CASE WHEN status IN ('interrupted', 'cancelled') THEN 1 ELSE 0 END) AS interrupted_runs,
            COALESCE(AVG(CASE WHEN status IN ('completed', 'success') THEN total_time_ms ELSE NULL END), 0) AS avg_duration_ms,
            COALESCE(AVG(total_sources), 0) AS avg_sources
        FROM telemetry_sessions
        WHERE created_at >= now() - interval '1 day' * ?
        """,
        [days_back],
    ).fetchone()

    report_count_row = conn.execute(
        """
        SELECT COUNT(*)
        FROM telemetry_sessions
        WHERE created_at >= now() - interval '1 day' * ?
        AND summary_json->>'has_report' = 'true'
        """,
        [days_back],
    ).fetchone()

    total_with_report = summary[0] if summary else 0
    report_count = report_count_row[0] if report_count_row else 0
    report_rate = (report_count / total_with_report * 100) if total_with_report > 0 else 0.0

    status_counts = conn.execute(
        """
        SELECT
            COALESCE(status, 'unknown') AS status,
            COUNT(*) AS count
        FROM telemetry_sessions
        WHERE created_at >= now() - interval '1 day' * ?
        GROUP BY status
        ORDER BY count DESC
        """,
        [days_back],
    ).fetchall()

    duration_by_status = conn.execute(
        """
        SELECT
            COALESCE(status, 'unknown') AS status,
            COALESCE(AVG(total_time_ms), 0) AS avg_duration_ms,
            MIN(total_time_ms) AS min_duration_ms,
            MAX(total_time_ms) AS max_duration_ms,
            COUNT(*) AS count
        FROM telemetry_sessions
        WHERE created_at >= now() - interval '1 day' * ?
        AND total_time_ms IS NOT NULL
        GROUP BY status
        ORDER BY count DESC
        """,
        [days_back],
    ).fetchall()

    sources_trend = conn.execute(
        """
        SELECT
            DATE_TRUNC('day', created_at) AS day,
            COUNT(*) AS run_count,
            COALESCE(AVG(total_sources), 0) AS avg_sources,
            SUM(total_sources) AS total_sources
        FROM telemetry_sessions
        WHERE created_at >= now() - interval '1 day' * ?
        GROUP BY DATE_TRUNC('day', created_at)
        ORDER BY day DESC
        """,
        [days_back],
    ).fetchall()

    daily_volume = conn.execute(
        """
        SELECT
            DATE_TRUNC('day', created_at) AS day,
            COUNT(*) AS total_runs,
            SUM(CASE WHEN status IN ('completed', 'success') THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN status IN ('failed', 'error') THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN status IN ('interrupted', 'cancelled') THEN 1 ELSE 0 END) AS interrupted
        FROM telemetry_sessions
        WHERE created_at >= now() - interval '1 day' * ?
        GROUP BY DATE_TRUNC('day', created_at)
        ORDER BY day DESC
        """,
        [days_back],
    ).fetchall()

    depth_dist = conn.execute(
        """
        SELECT
            COALESCE(summary_json->>'$.depth', 'unknown') AS depth,
            COUNT(*) AS count,
            COALESCE(AVG(total_time_ms), 0) AS avg_duration_ms
        FROM telemetry_sessions
        WHERE created_at >= now() - interval '1 day' * ?
        GROUP BY depth
        ORDER BY count DESC
        """,
        [days_back],
    ).fetchall()

    conn.close()

    session_store = SessionStore()
    saved_sessions = session_store.list_sessions()
    archived_count = sum(1 for s in saved_sessions if s.get("archived", False))
    active_count = sum(1 for s in saved_sessions if not s.get("archived", False))

    return {
        "summary": {
            "total_runs": summary[0] if summary else 0,
            "completed_runs": summary[1] if summary else 0,
            "failed_runs": summary[2] if summary else 0,
            "interrupted_runs": summary[3] if summary else 0,
            "avg_duration_ms": float(summary[4]) if summary else 0.0,
            "avg_sources": float(summary[5]) if summary else 0.0,
            "report_availability_rate": round(report_rate, 1),
            "archived_sessions": archived_count,
            "active_sessions": active_count,
        },
        "status_counts": [{"status": str(row[0]), "count": int(row[1])} for row in status_counts],
        "duration_by_status": [
            {
                "status": str(row[0]),
                "avg_duration_ms": float(row[1]) if row[1] else 0.0,
                "min_duration_ms": int(row[2]) if row[2] else 0,
                "max_duration_ms": int(row[3]) if row[3] else 0,
                "count": int(row[4]),
            }
            for row in duration_by_status
        ],
        "sources_trend": [
            {
                "day": serialize_timestamp(row[0]),
                "run_count": int(row[1]),
                "avg_sources": float(row[2]) if row[2] else 0.0,
                "total_sources": int(row[3]) if row[3] else 0,
            }
            for row in sources_trend
        ],
        "daily_volume": [
            {
                "day": serialize_timestamp(row[0]),
                "total_runs": int(row[1]),
                "completed": int(row[2]),
                "failed": int(row[3]),
                "interrupted": int(row[4]),
            }
            for row in daily_volume
        ],
        "depth_distribution": [
            {
                "depth": str(row[0]),
                "count": int(row[1]),
                "avg_duration_ms": float(row[2]) if row[2] else 0.0,
            }
            for row in depth_dist
        ],
    }


def register_misc_routes(app: FastAPI) -> None:
    """Register search cache, benchmark, theme, and analytics routes.

    Args:
        app: The FastAPI application instance.
    """

    # Search Cache Management Routes

    @app.get("/api/search-cache")
    async def list_search_cache_entries(
        include_expired: bool = Query(default=False, description="Include expired entries"),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> JSONResponse:
        """List search cache entries."""
        config = load_config()
        if not config.search_cache.enabled:
            return JSONResponse(
                content={"entries": [], "total": 0, "message": "Cache is disabled"},
            )

        db_path = config.search_cache.resolve_db_path()
        if not db_path.exists():
            return JSONResponse(
                content={"entries": [], "total": 0},
            )

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        entries = store.list_entries(
            include_expired=include_expired,
            limit=limit,
            offset=offset,
        )

        return JSONResponse(
            content={
                "entries": [
                    {
                        "cache_key": entry.cache_key,
                        "provider": entry.provider,
                        "normalized_query": entry.normalized_query,
                        "created_at": entry.created_at.isoformat(),
                        "expires_at": entry.expires_at.isoformat(),
                        "last_accessed_at": entry.last_accessed_at.isoformat(),
                        "hit_count": entry.hit_count,
                        "is_expired": entry.is_expired(),
                    }
                    for entry in entries
                ],
                "total": len(entries),
            }
        )

    @app.get("/api/search-cache/stats")
    async def get_search_cache_stats() -> JSONResponse:
        """Get search cache statistics."""
        config = load_config()
        cache_enabled = config.search_cache.enabled
        db_path = config.search_cache.resolve_db_path()

        response: dict[str, Any] = {
            "enabled": cache_enabled,
            "db_path": str(db_path),
            "ttl_seconds": config.search_cache.ttl_seconds,
            "max_entries": config.search_cache.max_entries,
        }

        if not cache_enabled:
            response.update(
                {
                    "total_entries": 0,
                    "active_entries": 0,
                    "expired_entries": 0,
                    "total_hits": 0,
                    "approximate_size_bytes": 0,
                    "db_exists": False,
                }
            )
            return JSONResponse(content=response)

        if not db_path.exists():
            response.update(
                {
                    "total_entries": 0,
                    "active_entries": 0,
                    "expired_entries": 0,
                    "total_hits": 0,
                    "approximate_size_bytes": 0,
                    "db_exists": False,
                }
            )
            return JSONResponse(content=response)

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        stats = store.get_stats()
        response.update(stats)
        response["db_exists"] = True

        return JSONResponse(content=response)

    @app.post("/api/search-cache/purge-expired")
    async def purge_expired_search_cache_entries() -> JSONResponse:
        """Purge expired entries from the search cache."""
        config = load_config()
        if not config.search_cache.enabled:
            return JSONResponse(
                content={"error": "Cache is disabled", "purged": 0},
                status_code=400,
            )

        db_path = config.search_cache.resolve_db_path()
        if not db_path.exists():
            return JSONResponse(
                content={"error": "Cache database not found", "purged": 0},
                status_code=404,
            )

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        purged = store.purge_expired()

        return JSONResponse(
            content={
                "purged": purged,
                "message": f"Purged {purged} expired entries",
            }
        )

    @app.delete("/api/search-cache/{cache_key}")
    async def delete_search_cache_entry(cache_key: str) -> JSONResponse:
        """Delete a specific cache entry."""
        config = load_config()
        if not config.search_cache.enabled:
            return JSONResponse(
                content={"error": "Cache is disabled", "deleted": False},
                status_code=400,
            )

        db_path = config.search_cache.resolve_db_path()
        if not db_path.exists():
            return JSONResponse(
                content={"error": "Cache database not found", "deleted": False},
                status_code=404,
            )

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        deleted = store.delete(cache_key)

        if not deleted:
            return JSONResponse(
                content={"error": f"Entry not found: {cache_key}", "deleted": False},
                status_code=404,
            )

        return JSONResponse(
            content={
                "cache_key": cache_key,
                "deleted": True,
            }
        )

    @app.delete("/api/search-cache")
    async def clear_search_cache() -> JSONResponse:
        """Clear all entries from the search cache."""
        config = load_config()
        if not config.search_cache.enabled:
            return JSONResponse(
                content={"error": "Cache is disabled", "cleared": 0},
                status_code=400,
            )

        db_path = config.search_cache.resolve_db_path()
        if not db_path.exists():
            return JSONResponse(
                content={"cleared": 0, "message": "Cache database does not exist"},
            )

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        cleared = store.clear()

        return JSONResponse(
            content={
                "cleared": cleared,
                "message": f"Cleared {cleared} entries from cache",
            }
        )

    @app.get("/api/benchmarks/corpus")
    async def get_benchmark_corpus() -> JSONResponse:
        """Get the benchmark corpus metadata."""
        try:
            corpus = load_benchmark_corpus()
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to load benchmark corpus: {str(e)}"},
                status_code=500,
            )

        return JSONResponse(content=corpus.model_dump(mode="json"))

    @app.get("/api/benchmarks/validate")
    async def validate_benchmark_corpus() -> JSONResponse:
        """Validate the benchmark corpus and return errors grouped by case."""
        try:
            corpus = load_benchmark_corpus()
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to load benchmark corpus: {str(e)}"},
                status_code=500,
            )

        from cc_deep_research.benchmark import validate_benchmark_corpus as _validate

        errors = _validate(corpus)
        return JSONResponse(
            content={
                "valid": len(errors) == 0,
                "errors": errors,
                "total_cases": len(corpus.cases),
            }
        )

    @app.get("/api/benchmarks/runs")
    async def list_benchmark_runs() -> JSONResponse:
        """List available benchmark runs."""
        runs = _list_benchmark_runs()
        return JSONResponse(
            content={
                "runs": runs,
                "total": len(runs),
            }
        )

    @app.get("/api/benchmarks/runs/{run_id}")
    async def get_benchmark_run(run_id: str) -> JSONResponse:
        """Get details for a specific benchmark run."""
        runs_dir = _get_benchmark_runs_dir()
        run_path = runs_dir / run_id

        if not run_path.exists():
            return JSONResponse(
                content={"error": f"Benchmark run not found: {run_id}"},
                status_code=404,
            )

        manifest_path = run_path / "manifest.json"
        if not manifest_path.exists():
            return JSONResponse(
                content={"error": "Invalid benchmark run: manifest.json not found"},
                status_code=404,
            )

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to read benchmark run: {str(e)}"},
                status_code=500,
            )

        return JSONResponse(content=manifest)

    @app.get("/api/benchmarks/runs/{run_id}/cases/{case_id}")
    async def get_benchmark_case_report(run_id: str, case_id: str) -> JSONResponse:
        """Get the report for a specific benchmark case."""
        runs_dir = _get_benchmark_runs_dir()
        case_path = runs_dir / run_id / "cases" / f"{case_id}.json"

        if not case_path.exists():
            return JSONResponse(
                content={"error": f"Benchmark case not found: {case_id}"},
                status_code=404,
            )

        try:
            case_report = json.loads(case_path.read_text(encoding="utf-8"))
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to read case report: {str(e)}"},
                status_code=500,
            )

        return JSONResponse(content=case_report)

    @app.post("/api/benchmarks/run")
    async def run_benchmark(
        workflow_mode: str = Query(default="staged", description="Research workflow mode"),
        depth: str = Query(default="standard", description="Research depth"),
        output_dir: str | None = Query(
            default=None, description="Output directory for benchmark run"
        ),
    ) -> JSONResponse:
        """Trigger a benchmark corpus run."""
        import asyncio

        from cc_deep_research.web_server import (
            get_backend_runtime,
            get_background_job_registry,
        )

        run_output_dir = (
            Path(output_dir)
            if output_dir
            else _get_benchmark_runs_dir() / Path(datetime.now(UTC).strftime("%Y%m%d_%H%M%S"))
        )
        job_registry = get_background_job_registry(app)
        job = job_registry.create_job(
            "benchmark.run",
            metadata={
                "workflow_mode": workflow_mode,
                "depth": depth,
                "output_dir": str(run_output_dir),
                "run_id": run_output_dir.name,
            },
        )

        async def run_benchmark_background() -> None:
            job_registry.mark_running(job.job_id)
            try:
                result = await asyncio.to_thread(
                    _run_benchmark_job,
                    workflow_mode=workflow_mode,
                    depth=depth,
                    output_dir=str(run_output_dir),
                    codex_runtime=get_backend_runtime(app).codex_runtime,
                )
                job_registry.mark_completed(job.job_id, result=result)
            except Exception as exc:
                job_registry.mark_failed(job.job_id, error=str(exc))

        task = asyncio.create_task(run_benchmark_background())
        job_registry.attach_task(job.job_id, task)
        return JSONResponse(
            content={
                "job_id": job.job_id,
                "kind": job.kind,
                "status": job.status,
                "run_id": run_output_dir.name,
                "output_dir": str(run_output_dir),
                "status_url": f"/api/jobs/{job.job_id}",
            },
            status_code=202,
        )

    @app.post("/api/benchmarks/compare")
    async def compare_benchmark(
        run1_path: str = Query(..., description="First benchmark run directory path"),
        run2_path: str = Query(..., description="Second benchmark run directory path"),
    ) -> JSONResponse:
        """Compare two benchmark runs and return delta metrics."""
        p1 = Path(run1_path)
        p2 = Path(run2_path)
        manifest1 = p1 / "manifest.json"
        manifest2 = p2 / "manifest.json"

        if not manifest1.exists():
            return JSONResponse(
                content={"error": f"Missing manifest.json in {run1_path}"},
                status_code=404,
            )
        if not manifest2.exists():
            return JSONResponse(
                content={"error": f"Missing manifest.json in {run2_path}"},
                status_code=404,
            )

        try:
            with manifest1.open() as f:
                run1 = BenchmarkRunReport.model_validate(json.load(f))
            with manifest2.open() as f:
                run2 = BenchmarkRunReport.model_validate(json.load(f))
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to load benchmark runs: {str(e)}"},
                status_code=500,
            )

        comparison = compare_benchmark_runs(run1, run2, run1_path=run1_path, run2_path=run2_path)

        return JSONResponse(content=comparison.model_dump(mode="json"))

    @app.get("/api/benchmarks/baselines")
    async def list_benchmarks_baselines() -> JSONResponse:
        """List all golden baselines."""
        baselines = list_baselines()
        return JSONResponse(
            content={
                "baselines": [b.to_dict() for b in baselines],
                "total": len(baselines),
            }
        )

    @app.get("/api/benchmarks/baselines/promoted")
    async def get_promoted_benchmark_baseline() -> JSONResponse:
        """Get the currently promoted (active) golden baseline."""
        baseline = get_promoted_baseline()
        if baseline is None:
            return JSONResponse(content={"baseline": None})
        return JSONResponse(content={"baseline": baseline.to_dict()})

    @app.get("/api/benchmarks/baselines/{run_id}")
    async def get_benchmark_baseline(run_id: str) -> JSONResponse:
        """Get a specific golden baseline."""
        baseline = get_baseline(run_id)
        if baseline is None:
            return JSONResponse(
                content={"error": f"Baseline not found: {run_id}"},
                status_code=404,
            )
        return JSONResponse(content=baseline.to_dict())

    @app.post("/api/benchmarks/baselines/{run_id}/promote")
    async def promote_benchmark_baseline(
        run_id: str,
        owner: str | None = Query(default=None, description="Baseline owner"),
        approval_note: str | None = Query(default=None, description="Approval note"),
    ) -> JSONResponse:
        """Promote a benchmark run to golden baseline status."""
        runs_dir = _get_benchmark_runs_dir()
        run_path = runs_dir / run_id
        manifest = run_path / "manifest.json"
        if not run_path.exists() or not manifest.exists():
            return JSONResponse(
                content={"error": f"Benchmark run not found: {run_id}"},
                status_code=404,
            )

        metadata = promote_to_baseline(
            run_id=run_id,
            run_path=str(run_path),
            owner=owner,
            approval_note=approval_note,
        )
        return JSONResponse(content=metadata.to_dict())

    @app.delete("/api/benchmarks/baselines/{run_id}")
    async def delete_benchmark_baseline(run_id: str) -> JSONResponse:
        """Remove golden baseline status from a run."""
        success = demote_baseline(run_id)
        if not success:
            return JSONResponse(
                content={"error": f"Baseline not found: {run_id}"},
                status_code=404,
            )
        return JSONResponse(content={"deleted": True, "run_id": run_id})

    @app.post("/api/benchmarks/gate")
    async def evaluate_benchmark_gate(
        baseline_run_id: str = Query(..., description="Baseline run ID"),
        candidate_run_id: str = Query(..., description="Candidate run ID"),
        min_pass_rate: float = Query(
            default=0.8, ge=0.0, le=1.0, description="Minimum pass rate threshold"
        ),
        min_validation_score: float = Query(
            default=0.6, ge=0.0, le=1.0, description="Minimum validation score threshold"
        ),
        max_latency_increase_ratio: float = Query(
            default=0.2, ge=0.0, description="Max fractional latency increase"
        ),
        override_notes: str | None = Query(
            default=None, description="Override notes if regression is accepted"
        ),
    ) -> JSONResponse:
        """Evaluate a candidate benchmark run against a named baseline."""
        baseline = load_baseline_run(baseline_run_id)
        if baseline is None:
            return JSONResponse(
                content={"error": f"Baseline not found: {baseline_run_id}"},
                status_code=404,
            )

        runs_dir = _get_benchmark_runs_dir()
        candidate_path = runs_dir / candidate_run_id
        manifest = candidate_path / "manifest.json"
        if not candidate_path.exists() or not manifest.exists():
            return JSONResponse(
                content={"error": f"Candidate run not found: {candidate_run_id}"},
                status_code=404,
            )

        try:
            with manifest.open() as f:
                candidate = BenchmarkRunReport.model_validate(json.load(f))
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to load candidate run: {str(e)}"},
                status_code=500,
            )

        thresholds = BenchmarkGateThresholds(
            min_pass_rate=min_pass_rate,
            min_validation_score=min_validation_score,
            max_latency_increase_ratio=max_latency_increase_ratio,
        )

        from cc_deep_research.benchmark import evaluate_benchmark_gate as _evaluate_gate

        result = _evaluate_gate(
            baseline,
            candidate,
            thresholds,
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            override_notes=override_notes,
        )

        return JSONResponse(content=result.model_dump(mode="json"))

    @app.get("/api/themes")
    async def list_research_themes() -> JSONResponse:
        """List available research themes for the dashboard."""
        themes = _get_research_theme_list()
        return JSONResponse(content={"themes": themes, "total": len(themes)})

    @app.get("/api/analytics")
    async def get_analytics(
        days_back: int = Query(default=30, ge=1, le=365, description="Days of history to analyze"),
    ) -> JSONResponse:
        """Get aggregate analytics data for operational insights."""
        analytics = _query_analytics_data(days_back=days_back)
        return JSONResponse(content=analytics)

    @app.get("/api/benchmarks/trends")
    async def get_benchmark_trends(
        limit: int = Query(default=10, ge=1, le=50, description="Number of recent runs to include"),
    ) -> JSONResponse:
        """Get evaluation trends across recent benchmark runs.

        Returns per-run summaries including quality score, pass rate, latency, and cost.
        """
        runs_dir = _get_benchmark_runs_dir()
        runs: list[dict[str, Any]] = []

        if runs_dir.exists():
            for run_path in sorted(
                runs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                if not run_path.is_dir():
                    continue
                manifest_path = run_path / "manifest.json"
                scorecard_path = run_path / "scorecard.json"
                if not manifest_path.exists() or not scorecard_path.exists():
                    continue

                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
                except Exception:
                    continue

                pass_count = sum(
                    1 for c in manifest.get("cases", []) if c.get("stop_reason") == "success"
                )
                total = scorecard.get("total_cases", 0)
                runs.append(
                    {
                        "run_id": run_path.name,
                        "generated_at": manifest.get("generated_at"),
                        "corpus_version": manifest.get("corpus_version"),
                        "workflow_mode": scorecard.get("workflow_mode"),
                        "total_cases": total,
                        "pass_count": pass_count,
                        "pass_rate": round(pass_count / total, 3) if total > 0 else None,
                        "average_validation_score": scorecard.get("average_validation_score"),
                        "average_latency_ms": scorecard.get("average_latency_ms"),
                        "average_report_quality_score": scorecard.get(
                            "average_report_quality_score"
                        ),
                        "average_source_count": scorecard.get("average_source_count"),
                        "date_sensitive_cases": scorecard.get("date_sensitive_cases"),
                        "stop_reasons": scorecard.get("stop_reasons", {}),
                        "categories": scorecard.get("categories", {}),
                    }
                )

                if len(runs) >= limit:
                    break

        return JSONResponse(content={"runs": runs, "total": len(runs)})


def _get_benchmark_runs_dir() -> Path:
    """Return the default benchmark runs directory."""
    return Path(os.environ.get("BENCHMARK_RUNS_DIR", "benchmark_runs"))


def _list_benchmark_runs() -> list[dict[str, Any]]:
    """List available benchmark runs from the filesystem."""
    runs_dir = _get_benchmark_runs_dir()
    runs: list[dict[str, Any]] = []

    if not runs_dir.exists():
        return runs

    for run_path in sorted(runs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not run_path.is_dir():
            continue

        manifest_path = run_path / "manifest.json"
        scorecard_path = run_path / "scorecard.json"

        run_info: dict[str, Any] = {
            "run_id": run_path.name,
            "path": str(run_path),
        }

        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                run_info["corpus_version"] = manifest.get("corpus_version")
                run_info["generated_at"] = manifest.get("generated_at")
                run_info["configuration"] = manifest.get("configuration", {})
            except Exception:
                pass

        if scorecard_path.exists():
            try:
                scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
                run_info["total_cases"] = scorecard.get("total_cases", 0)
                run_info["average_validation_score"] = scorecard.get("average_validation_score")
                run_info["average_latency_ms"] = scorecard.get("average_latency_ms")
            except Exception:
                pass

        runs.append(run_info)

    return runs
