"""YAML persistence for content-gen telemetry and operating fitness metrics.

P7-T1: Persists signals needed to judge content outcomes and workflow speed.
P7-T3: Tracks operating fitness metrics including cycle time, kill rate,
      reuse rate, and cost per published asset.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import (
    ContentGenRunMetrics,
    OperatingFitnessMetrics,
    RuleVersion,
    RuleVersionHistory,
)
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _serialize_model_to_dict(model: Any) -> dict[str, Any]:
    """Serialize a Pydantic model to a plain dict, converting enums to string values."""
    from enum import Enum

    def _convert_value(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {k: _convert_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_convert_value(item) for item in value]
        return value

    data = model.model_dump(exclude_none=True)
    return _convert_value(data)


class ContentGenTelemetryStore:
    """Store and query content-gen run metrics and operating fitness.

    P7-T1: Captures signals that link content outcomes to workflow speed,
    including stage timing, selection decisions, and release state.

    P7-T3: Provides metrics for cycle time, kill rate, reuse rate, and
    cost per published asset.
    """

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="content_gen_telemetry_path",
            default_name="content_gen_telemetry.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    # ---------------------------------------------------------------------------
    # Run Metrics
    # ---------------------------------------------------------------------------

    def load_run_metrics(self) -> list[ContentGenRunMetrics]:
        """Load all stored run metrics."""
        if not self._path.exists():
            return []
        data = yaml.safe_load(self._path.read_text()) or {}
        runs_data = data.get("run_metrics", [])
        return [ContentGenRunMetrics.model_validate(run) for run in runs_data]

    def save_run_metrics(self, runs: list[ContentGenRunMetrics]) -> None:
        """Persist run metrics to disk, preserving other data."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._load_base_data()
        operating_fitness = existing.get("operating_fitness", {})
        rule_version_history = existing.get("rule_version_history", {})
        data = {
            "run_metrics": [_serialize_model_to_dict(run) for run in runs],
            "operating_fitness": operating_fitness,
            "rule_version_history": rule_version_history,
            "last_updated": _now_iso(),
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_run_metrics(self, run: ContentGenRunMetrics) -> None:
        """Add a single run's metrics to the store."""
        existing = self.load_run_metrics()
        existing.append(run)
        self.save_run_metrics(existing)

    def upsert_run_metrics(self, run: ContentGenRunMetrics) -> None:
        """Insert or replace run metrics for a pipeline run."""
        existing = self.load_run_metrics()
        replaced = False
        for index, current in enumerate(existing):
            if current.run_id == run.run_id:
                existing[index] = run
                replaced = True
                break
        if not replaced:
            existing.append(run)
        self.save_run_metrics(existing)

    # ---------------------------------------------------------------------------
    # Operating Fitness
    # ---------------------------------------------------------------------------

    def load_operating_fitness(self) -> OperatingFitnessMetrics:
        """Load current operating fitness metrics."""
        if not self._path.exists():
            return OperatingFitnessMetrics()
        data = yaml.safe_load(self._path.read_text()) or {}
        fitness_data = data.get("operating_fitness", {})
        return OperatingFitnessMetrics.model_validate(fitness_data) if fitness_data else OperatingFitnessMetrics()

    def save_operating_fitness(self, metrics: OperatingFitnessMetrics) -> None:
        """Persist operating fitness metrics."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._load_base_data()
        run_metrics = existing.get("run_metrics", [])
        rule_version_history = existing.get("rule_version_history", {})
        data = {
            "run_metrics": run_metrics,
            "operating_fitness": _serialize_model_to_dict(metrics),
            "rule_version_history": rule_version_history,
            "last_updated": _now_iso(),
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def compute_operating_fitness(
        self,
        *,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> OperatingFitnessMetrics:
        """Compute operating fitness metrics from stored run data.

        P7-T3: Derives cycle time, kill rate, reuse rate, and cost metrics
        from actual run history.
        """
        runs = self.load_run_metrics()

        # Filter by period if specified
        if period_start:
            runs = [r for r in runs if r.created_at >= period_start]
        if period_end:
            runs = [r for r in runs if r.created_at <= period_end]

        if not runs:
            return OperatingFitnessMetrics()

        # Calculate cycle time stats
        cycle_times = [r.total_cycle_time_ms for r in runs if r.total_cycle_time_ms > 0]
        sorted_times = sorted(cycle_times)
        median_idx = len(sorted_times) // 2

        avg_cycle = sum(sorted_times) / len(sorted_times) if sorted_times else 0.0
        median_cycle = sorted_times[median_idx] if sorted_times else 0.0
        p95_idx = int(len(sorted_times) * 0.95)
        p95_cycle = sorted_times[p95_idx] if sorted_times else 0.0

        # Count by release state
        total = len(runs)
        killed_early = sum(
            1 for r in runs
            if r.release_state in ("killed_early",)
        )
        killed_late = sum(
            1 for r in runs
            if r.release_state in ("killed_late",)
        )
        published = sum(1 for r in runs if r.release_state == "published")
        held = sum(1 for r in runs if r.release_state == "held")
        recycled = sum(1 for r in runs if r.release_state == "recycled_for_reuse")

        # Reuse metrics
        reuse_candidates = sum(1 for r in runs if r.reuse_recommended)
        reuse_applied = sum(
            1 for r in runs
            if r.reuse_recommended and r.release_state == "recycled_for_reuse"
        )

        # Cost metrics
        total_cost = sum(r.estimated_cost_cents for r in runs if r.estimated_cost_cents)
        avg_cost_published = total_cost / published if published else 0.0
        avg_cost_killed = total_cost / (killed_early + killed_late) if (killed_early + killed_late) else 0.0

        # Throughput (assume 7-day window if period not specified)
        period_days = 7.0
        if period_start and period_end:
            try:
                start_dt = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
                period_days = max(1.0, (end_dt - start_dt).days)
            except ValueError:
                period_days = 7.0

        weeks = period_days / 7.0
        ideas_per_week = total / weeks if weeks > 0 else 0.0
        published_per_week = published / weeks if weeks > 0 else 0.0

        metrics = OperatingFitnessMetrics(
            avg_cycle_time_ms=avg_cycle,
            median_cycle_time_ms=median_cycle,
            p95_cycle_time_ms=p95_cycle,
            fastest_cycle_time_ms=sorted_times[0] if sorted_times else 0,
            slowest_cycle_time_ms=sorted_times[-1] if sorted_times else 0,
            total_ideas_evaluated=total,
            ideas_killed_early=killed_early,
            ideas_killed_late=killed_late,
            ideas_published=published,
            ideas_held=held,
            ideas_recycled=recycled,
            reuse_candidates_identified=reuse_candidates,
            reuse_candidates_applied=reuse_applied,
            total_estimated_cost_cents=total_cost,
            avg_cost_per_published=avg_cost_published,
            avg_cost_per_killed=avg_cost_killed,
            ideas_per_week=ideas_per_week,
            published_per_week=published_per_week,
            period_start=period_start or runs[0].created_at if runs else "",
            period_end=period_end or runs[-1].created_at if runs else "",
            total_runs=total,
        )

        self.save_operating_fitness(metrics)
        return metrics

    # ---------------------------------------------------------------------------
    # Rule Version History
    # ---------------------------------------------------------------------------

    def load_rule_version_history(self) -> RuleVersionHistory:
        """Load rule version history."""
        if not self._path.exists():
            return RuleVersionHistory()
        data = yaml.safe_load(self._path.read_text()) or {}
        history_data = data.get("rule_version_history", {})
        return RuleVersionHistory.model_validate(history_data) if history_data else RuleVersionHistory()

    def save_rule_version_history(self, history: RuleVersionHistory) -> None:
        """Persist rule version history."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._load_base_data()
        run_metrics = existing.get("run_metrics", [])
        operating_fitness = existing.get("operating_fitness", {})
        data = {
            "run_metrics": run_metrics,
            "operating_fitness": operating_fitness,
            "rule_version_history": _serialize_model_to_dict(history),
            "last_updated": _now_iso(),
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_rule_version(self, version: RuleVersion) -> None:
        """Add a new rule version to the history."""
        history = self.load_rule_version_history()
        history.versions.append(version)
        self.save_rule_version_history(history)

    def record_rule_change(
        self,
        kind: str,
        operation: str,
        change_summary: str,
        *,
        previous_value: str = "",
        new_value: str = "",
        source_learning_ids: list[str] | None = None,
        source_content_ids: list[str] | None = None,
        approved_by: str = "",
    ) -> RuleVersion:
        """Record a rule change and persist it.

        P7-T2: Records versioned rule changes so operators can see when
        guidance changed and scoring/packaging can be traced to results.
        """
        from cc_deep_research.content_gen.models import (
            RuleChangeOperation,
            RuleVersion,
            RuleVersionKind,
        )

        version = RuleVersion(
            kind=RuleVersionKind(kind),
            operation=RuleChangeOperation(operation),
            change_summary=change_summary,
            previous_value=previous_value,
            new_value=new_value,
            source_learning_ids=source_learning_ids or [],
            source_content_ids=source_content_ids or [],
            approved_by=approved_by,
            created_at=_now_iso(),
        )
        self.add_rule_version(version)
        return version

    # ---------------------------------------------------------------------------
    # Query Helpers
    # ---------------------------------------------------------------------------

    def get_runs_by_release_state(
        self,
        release_state: str,
    ) -> list[ContentGenRunMetrics]:
        """Get all runs with a specific release state."""
        runs = self.load_run_metrics()
        return [r for r in runs if r.release_state == release_state]

    def get_fast_cycles(
        self,
        effort_tier: str | None = None,
    ) -> list[ContentGenRunMetrics]:
        """Get runs that completed faster than their effort tier threshold."""
        runs = self.load_run_metrics()
        results = [r for r in runs if r.is_fast_cycle]
        if effort_tier:
            results = [r for r in results if r.effort_tier == effort_tier]
        return results

    def get_top_performers(
        self,
        limit: int = 10,
        min_views: int = 0,
    ) -> list[ContentGenRunMetrics]:
        """Get top performing runs by view count."""
        runs = self.load_run_metrics()
        filtered = [r for r in runs if r.view_count >= min_views]
        return sorted(filtered, key=lambda r: r.view_count, reverse=True)[:limit]

    def _load_base_data(self) -> dict[str, Any]:
        """Load base data without full model parsing (for preserving existing data)."""
        if not self._path.exists():
            return {}
        return yaml.safe_load(self._path.read_text()) or {}

    # ---------------------------------------------------------------------------
    # Integration with PerformanceLearningStore
    # ---------------------------------------------------------------------------

    def sync_from_performance_learning(
        self,
        video_id: str,
        analysis: Any,  # PerformanceAnalysis
        metrics: dict[str, Any],
    ) -> None:
        """Update run metrics when performance analysis is available.

        Links the performance analysis back to the original run metrics
        so we can track audience outcomes alongside workflow speed.
        """
        runs = self.load_run_metrics()
        # Find the run by video_id or update the most recent
        for run in reversed(runs):
            if run.idea_id == video_id or run.run_id == video_id:
                run.view_count = metrics.get("views", 0)
                run.engagement_rate = metrics.get("engagement_rate", 0.0)
                run.analyzed_at = _now_iso()
                break
        self.save_run_metrics(runs)
