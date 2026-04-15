"""YAML persistence for opportunity planning learnings and metrics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import (
    PlanningLearning,
    PlanningLearningCategory,
    PlanningMetrics,
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


class PlanningLearningStore:
    """Load and save opportunity planning learnings and metrics to a YAML file.

    Provides controlled paths for:
    - Storing raw learnings from opportunity planning runs
    - Tracking planning quality metrics over time
    - Querying learnings by category for use in future planning
    """

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="planning_learning_path",
            default_name="planning_learnings.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load_learnings(self) -> list[PlanningLearning]:
        """Load all stored planning learnings from disk."""
        if not self._path.exists():
            return []
        data = yaml.safe_load(self._path.read_text()) or {}
        learnings_data = data.get("learnings", [])
        return [PlanningLearning.model_validate(item) for item in learnings_data]

    def load_metrics(self) -> PlanningMetrics:
        """Load current planning metrics."""
        if not self._path.exists():
            return PlanningMetrics()
        data = yaml.safe_load(self._path.read_text()) or {}
        metrics_data = data.get("metrics", {})
        return PlanningMetrics.model_validate(metrics_data) if metrics_data else PlanningMetrics()

    def save_learning(self, learning: PlanningLearning) -> None:
        """Persist a single planning learning, preserving existing data."""
        existing = self.load_learnings()
        existing.append(learning)
        self._save_all_learnings(existing)

    def save_learnings(self, learnings: list[PlanningLearning]) -> None:
        """Persist a list of planning learnings, preserving existing data."""
        existing = self.load_learnings()
        existing.extend(learnings)
        self._save_all_learnings(existing)

    def _save_all_learnings(self, learnings: list[PlanningLearning]) -> None:
        """Save full learnings list, preserving metrics."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing_metrics = self.load_metrics()
        data = {
            "learnings": [_serialize_model_to_dict(item) for item in learnings],
            "metrics": _serialize_model_to_dict(existing_metrics),
            "last_updated": _now_iso(),
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def save_metrics(self, metrics: PlanningMetrics) -> None:
        """Persist planning metrics, preserving learnings."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing_learnings = self.load_learnings()
        data = {
            "learnings": [_serialize_model_to_dict(learn) for learn in existing_learnings],
            "metrics": _serialize_model_to_dict(metrics),
            "last_updated": _now_iso(),
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def increment_metric(
        self,
        *,
        acceptable: bool = False,
        rewritten: bool = False,
        approved: bool = False,
        converted: bool = False,
    ) -> PlanningMetrics:
        """Increment one or more planning metric counters atomically."""
        metrics = self.load_metrics()
        metrics.total_briefs += 1
        if acceptable:
            metrics.acceptable_briefs += 1
        if rewritten:
            metrics.rewritten_briefs += 1
        if approved:
            metrics.approved_briefs += 1
        if converted:
            metrics.converted_to_production += 1
        self.save_metrics(metrics)
        return metrics

    def get_active_learnings(
        self,
        *,
        category: PlanningLearningCategory | None = None,
    ) -> list[PlanningLearning]:
        """Query active learnings by optional category filter."""
        learnings = self.load_learnings()
        results = [learn for learn in learnings if learn.is_active]
        if category is not None:
            results = [learn for learn in results if learn.category == category]
        return results

    def get_reviewed_learnings(self) -> list[PlanningLearning]:
        """Get learnings that have been operator-reviewed and are ready for use."""
        return [learn for learn in self.load_learnings() if learn.is_active and learn.operator_reviewed]

    def extract_learning_from_brief(
        self,
        brief: Any,  # OpportunityBrief
        *,
        outcome_notes: str = "",
    ) -> PlanningLearning | None:
        """Extract a planning learning from an opportunity brief.

        This is called after a brief has been used and we want to record
        what made it good or bad for future planning.

        Args:
            brief: The OpportunityBrief to extract learning from
            outcome_notes: Notes on how the brief performed downstream

        Returns:
            PlanningLearning extracted from the brief, or None if extraction fails
        """
        if not brief:
            return None

        now = _now_iso()
        learning_id = f"planlearn_{now[:10]}"
        category = PlanningLearningCategory.BRIEF_SPECIFICITY

        # Determine category based on brief properties
        if not brief.primary_audience_segment:
            category = PlanningLearningCategory.AUDIENCE_DEFINITION
        elif not brief.research_hypotheses:
            category = PlanningLearningCategory.HYPOTHESIS_QUALITY
        elif not brief.success_criteria:
            category = PlanningLearningCategory.SUCCESS_CRITERIA
        elif len(brief.sub_angles) <= 1:
            category = PlanningLearningCategory.SUB_ANGLE_DISTINCTION

        # Build pattern description from what we can observe
        pattern_parts = []
        if brief.goal:
            pattern_parts.append(f"goal={brief.goal[:50]}")
        if brief.primary_audience_segment:
            pattern_parts.append(f"audience={brief.primary_audience_segment[:50]}")
        if brief.sub_angles:
            pattern_parts.append(f"sub_angles={len(brief.sub_angles)}")
        if brief.research_hypotheses:
            pattern_parts.append(f"hypotheses={len(brief.research_hypotheses)}")

        pattern = "; ".join(pattern_parts) if pattern_parts else "unknown"
        implication = f"Brief had category {category.value} — " + (outcome_notes or "see notes")
        guidance = f"Apply same pattern to future briefs for category {category.value}"

        return PlanningLearning(
            learning_id=learning_id,
            category=category,
            pattern=pattern,
            implication=implication,
            guidance=guidance,
            source_brief_ids=[getattr(brief, "brief_id", "") or ""],
            is_active=True,
            created_at=now,
        )
