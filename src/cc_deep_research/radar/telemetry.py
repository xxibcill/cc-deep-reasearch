"""Telemetry and analytics for Opportunity Radar.

This module provides:
- RadarTelemetryStore: aggregates feedback and conversion metrics
- get_radar_analytics(): computes summary statistics for operators
- get_conversion_funnel(): computes funnel data for visualization
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path
from cc_deep_research.radar._path_utils import allowed_prefixes, is_safe_path
from cc_deep_research.radar.models import (
    FeedbackType,
    Opportunity,
    OpportunityFeedback,
    RadarAnalytics,
    WorkflowType,
)
from cc_deep_research.radar.storage import RadarStore

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

RADAR_ANALYTICS_SUBDIR = "radar_analytics"


def _default_analytics_dir() -> Path:
    """Return the default radar analytics directory."""
    return get_default_config_path().parent / RADAR_ANALYTICS_SUBDIR


def resolve_analytics_file_path(
    file_key: str,
    explicit_path: Path | None = None,
) -> Path:
    """Resolve an analytics file path from explicit path or defaults."""
    if explicit_path is not None:
        if not is_safe_path(explicit_path):
            raise ValueError(f"Explicit path {explicit_path} escapes allowed directories")
        return explicit_path

    filename = f"radar_{file_key}.yaml"
    return _default_analytics_dir() / filename


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(tz=UTC).isoformat()


# ---------------------------------------------------------------------------
# Radar Telemetry Store
# ---------------------------------------------------------------------------


class RadarTelemetryStore:
    """Aggregates feedback and conversion metrics for the Radar feature.

    This store computes analytics on top of the raw RadarStore data,
    providing summary statistics for operators to understand performance
    and tune the system over time.
    """

    def __init__(
        self,
        store: RadarStore | None = None,
        analytics_dir: Path | None = None,
    ) -> None:
        """Initialize the telemetry store.

        Args:
            store: RadarStore to query for raw data. Defaults to new RadarStore.
            analytics_dir: Optional explicit directory for analytics files.
        """
        self._store = store or RadarStore()
        if analytics_dir is not None:
            if not is_safe_path(analytics_dir):
                raise ValueError(f"analytics_dir {analytics_dir} escapes allowed directories")
            self._analytics_dir = analytics_dir
        else:
            self._analytics_dir = _default_analytics_dir()

        self._analytics_dir.mkdir(parents=True, exist_ok=True)

    def get_analytics(self) -> RadarAnalytics:
        """Compute aggregated analytics for the Radar feature.

        Returns:
            RadarAnalytics with summary statistics.
        """
        opportunities = self._store.load_opportunities().opportunities
        feedback_entries = self._store.load_feedback().feedback_entries
        workflow_links = self._store.load_workflow_links().links
        scores = self._store.load_scores().scores

        # Count by status
        status_counts: Counter[str] = Counter()
        for opp in opportunities:
            status_counts[opp.status.value] += 1

        # Count by type
        type_counts: Counter[str] = Counter()
        for opp in opportunities:
            type_counts[opp.opportunity_type.value] += 1

        # Count feedback by type
        feedback_counts: Counter[str] = Counter()
        for fb in feedback_entries:
            feedback_counts[fb.feedback_type.value] += 1

        # Compute conversion rates using unique opportunities per workflow type.
        acted_on_count = status_counts.get("acted_on", 0)
        workflow_opportunities = {
            WorkflowType.RESEARCH_RUN: {
                wl.opportunity_id
                for wl in workflow_links
                if wl.workflow_type == WorkflowType.RESEARCH_RUN
            },
            WorkflowType.BRIEF: {
                wl.opportunity_id
                for wl in workflow_links
                if wl.workflow_type == WorkflowType.BRIEF
            },
            WorkflowType.BACKLOG_ITEM: {
                wl.opportunity_id
                for wl in workflow_links
                if wl.workflow_type == WorkflowType.BACKLOG_ITEM
            },
            WorkflowType.CONTENT_PIPELINE: {
                wl.opportunity_id
                for wl in workflow_links
                if wl.workflow_type == WorkflowType.CONTENT_PIPELINE
            },
        }
        conversion_rates = {
            "research_run": (
                len(workflow_opportunities[WorkflowType.RESEARCH_RUN]) / acted_on_count
                if acted_on_count > 0
                else 0.0
            ),
            "brief": (
                len(workflow_opportunities[WorkflowType.BRIEF]) / acted_on_count
                if acted_on_count > 0
                else 0.0
            ),
            "backlog_item": (
                len(workflow_opportunities[WorkflowType.BACKLOG_ITEM]) / acted_on_count
                if acted_on_count > 0
                else 0.0
            ),
            "content_pipeline": (
                len(workflow_opportunities[WorkflowType.CONTENT_PIPELINE]) / acted_on_count
                if acted_on_count > 0
                else 0.0
            ),
        }

        # Compute average time to action
        avg_time_to_action = self._compute_avg_time_to_action(opportunities, feedback_entries)

        # Top opportunity types
        top_types = type_counts.most_common(5)

        return RadarAnalytics(
            total_opportunities=len(opportunities),
            opportunities_by_status=dict(status_counts),
            opportunities_by_type=dict(type_counts),
            feedback_counts=dict(feedback_counts),
            conversion_rates=conversion_rates,
            avg_time_to_action_hours=avg_time_to_action,
            top_opportunity_types=top_types,
        )

    def _compute_avg_time_to_action(
        self,
        opportunities: list[Opportunity],
        feedback_entries: list[OpportunityFeedback],
    ) -> float | None:
        """Compute average hours from creation to first action.

        Args:
            opportunities: All opportunities.
            feedback_entries: All feedback entries.

        Returns:
            Average hours to first action, or None if no data.
        """
        action_times: list[float] = []

        for opp in opportunities:
            # Find creation time
            try:
                created = datetime.fromisoformat(opp.created_at)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
            except ValueError:
                continue

            # Find first action (converted_to_research or converted_to_content)
            opp_feedback = [f for f in feedback_entries if f.opportunity_id == opp.id]
            converted = [
                f for f in opp_feedback
                if f.feedback_type in (FeedbackType.CONVERTED_TO_RESEARCH, FeedbackType.CONVERTED_TO_CONTENT)
            ]

            if not converted:
                continue

            # Get earliest conversion
            converted.sort(key=lambda f: f.created_at)
            try:
                first_action = datetime.fromisoformat(converted[0].created_at)
                if first_action.tzinfo is None:
                    first_action = first_action.replace(tzinfo=UTC)
            except ValueError:
                continue

            hours = (first_action - created).total_seconds() / 3600
            action_times.append(hours)

        if not action_times:
            return None

        return sum(action_times) / len(action_times)

    def get_conversion_funnel(self) -> dict[str, Any]:
        """Compute conversion funnel data.

        Returns:
            Funnel data with counts at each stage.
        """
        opportunities = self._store.load_opportunities().opportunities
        status_counts: Counter[str] = Counter()

        for opp in opportunities:
            status_counts[opp.status.value] += 1

        # Funnel stages in order
        funnel = [
            {"stage": "new", "label": "New", "count": status_counts.get("new", 0)},
            {"stage": "saved", "label": "Saved", "count": status_counts.get("saved", 0)},
            {"stage": "monitoring", "label": "Monitoring", "count": status_counts.get("monitoring", 0)},
            {"stage": "acted_on", "label": "Acted On", "count": status_counts.get("acted_on", 0)},
        ]

        return {
            "funnel": funnel,
            "total": len(opportunities),
        }

    def get_feedback_trends(self, days_back: int = 30) -> dict[str, Any]:
        """Compute feedback trends over time.

        Args:
            days_back: Number of days to look back.

        Returns:
            Feedback counts by day and type.
        """
        feedback_entries = self._store.load_feedback().feedback_entries
        cutoff = datetime.now(tz=UTC).timestamp() - (days_back * 24 * 3600)

        # Group by day and type
        daily_counts: dict[str, Counter[str]] = {}

        for fb in feedback_entries:
            try:
                fb_time = datetime.fromisoformat(fb.created_at)
                if fb_time.tzinfo is None:
                    fb_time = fb_time.replace(tzinfo=UTC)
            except ValueError:
                continue

            if fb_time.timestamp() < cutoff:
                continue

            day_key = fb_time.strftime("%Y-%m-%d")
            if day_key not in daily_counts:
                daily_counts[day_key] = Counter()
            daily_counts[day_key][fb.feedback_type.value] += 1

        return {
            "daily_counts": {
                day: dict(counts) for day, counts in sorted(daily_counts.items())
            },
            "days_back": days_back,
        }

    def get_score_distribution(self) -> dict[str, Any]:
        """Get the distribution of opportunity scores.

        Returns:
            Score distribution buckets.
        """
        scores = self._store.load_scores().scores

        buckets = {
            "80-100": 0,
            "60-79": 0,
            "40-59": 0,
            "20-39": 0,
            "0-19": 0,
        }

        for score in scores:
            if score.total_score >= 80:
                buckets["80-100"] += 1
            elif score.total_score >= 60:
                buckets["60-79"] += 1
            elif score.total_score >= 40:
                buckets["40-59"] += 1
            elif score.total_score >= 20:
                buckets["20-39"] += 1
            else:
                buckets["0-19"] += 1

        total = len(scores)
        return {
            "distribution": buckets,
            "total": total,
            "avg_score": sum(s.total_score for s in scores) / total if total > 0 else 0,
        }


def get_radar_analytics() -> RadarAnalytics:
    """Convenience function to get analytics from default store."""
    store = RadarStore()
    telemetry = RadarTelemetryStore(store=store)
    return telemetry.get_analytics()


def get_radar_conversion_funnel() -> dict[str, Any]:
    """Convenience function to get funnel data from default store."""
    store = RadarStore()
    telemetry = RadarTelemetryStore(store=store)
    return telemetry.get_conversion_funnel()


def get_radar_feedback_trends(days_back: int = 30) -> dict[str, Any]:
    """Convenience function to get feedback trends from default store."""
    store = RadarStore()
    telemetry = RadarTelemetryStore(store=store)
    return telemetry.get_feedback_trends(days_back)
