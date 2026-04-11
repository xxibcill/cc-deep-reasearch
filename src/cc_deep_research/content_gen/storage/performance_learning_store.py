"""YAML persistence for performance learnings."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import (
    LearningCategory,
    LearningDurability,
    PerformanceLearning,
    PerformanceLearningSet,
    StrategyPerformanceGuidance,
)
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _serialize_model_to_dict(model: Any) -> dict[str, Any]:
    """Serialize a Pydantic model to a plain dict, converting enums to string values.

    This ensures YAML serialization works correctly with safe_load.
    """
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


class PerformanceLearningStore:
    """Load and save performance learnings to a YAML file.

    Provides controlled paths for:
    - Storing raw learnings from performance analysis
    - Applying learnings to strategy guidance (operator-gated)
    - Querying learnings by category, durability, or platform
    """

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="performance_learning_path",
            default_name="performance_learnings.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load_raw_learnings(self) -> list[PerformanceLearning]:
        """Load all stored performance learnings from disk."""
        if not self._path.exists():
            return []
        data = yaml.safe_load(self._path.read_text()) or {}
        learnings_data = data.get("learnings", [])
        return [PerformanceLearning.model_validate(learning) for learning in learnings_data]

    def load_strategy_guidance(self) -> StrategyPerformanceGuidance:
        """Load the durable strategy guidance derived from learnings."""
        if not self._path.exists():
            return StrategyPerformanceGuidance()
        data = yaml.safe_load(self._path.read_text()) or {}
        guidance_data = data.get("strategy_guidance", {})
        return StrategyPerformanceGuidance.model_validate(guidance_data)

    def save_raw_learnings(self, learnings: list[PerformanceLearning]) -> None:
        """Persist raw performance learnings to disk, preserving existing strategy guidance."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Preserve existing strategy guidance when updating learnings
        existing_guidance = self.load_strategy_guidance()
        data = {
            "learnings": [_serialize_model_to_dict(learning) for learning in learnings],
            "strategy_guidance": _serialize_model_to_dict(existing_guidance),
            "last_updated": _now_iso(),
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def save_strategy_guidance(self, guidance: StrategyPerformanceGuidance) -> None:
        """Persist durable strategy guidance to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Preserve learnings when updating guidance
        existing_learnings = self.load_raw_learnings()
        data = {
            "learnings": [_serialize_model_to_dict(learning) for learning in existing_learnings],
            "strategy_guidance": _serialize_model_to_dict(guidance),
            "last_updated": _now_iso(),
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    # ---------------------------------------------------------------------------
    # Learning extraction from PerformanceAnalysis
    # ---------------------------------------------------------------------------

    def extract_learnings_from_analysis(
        self,
        video_id: str,
        analysis: Any,  # PerformanceAnalysis
        *,
        platform: str = "",
    ) -> PerformanceLearningSet:
        """Convert a PerformanceAnalysis into structured learnings.

        This is additive — it creates new learnings without modifying existing ones.
        """
        from cc_deep_research.content_gen.models import PerformanceLearning

        learnings: list[PerformanceLearning] = []
        now = _now_iso()

        # Extract hook learnings
        if analysis.hook_diagnosis:
            durability = self._infer_durability(analysis.hook_diagnosis, analysis.metrics)
            learnings.append(
                PerformanceLearning(
                    category=LearningCategory.HOOK,
                    durability=durability,
                    observation=analysis.hook_diagnosis,
                    implication="The hook determines initial retention and click-through.",
                    guidance=self._derive_hook_guidance(analysis.hook_diagnosis),
                    source_video_ids=[video_id],
                    source_metrics=dict(analysis.metrics or {}),
                    created_at=now,
                    updated_at=now,
                    platform=platform,
                )
            )

        # Extract what worked learnings
        for item in (analysis.what_worked or []):
            learnings.append(
                PerformanceLearning(
                    category=self._categorize_from_text(item, categories_guess=[
                        (LearningCategory.HOOK, ["hook", "opening", "first"]),
                        (LearningCategory.Framing, ["framing", "angle", "perspective"]),
                        (LearningCategory.AUDIENCE, ["audience", "resonated"]),
                        (LearningCategory.PROOF, ["proof", "evidence", "credibility"]),
                        (LearningCategory.FORMAT, ["format", "structure", "length"]),
                        (LearningCategory.PACING, ["pacing", "retention", "flow"]),
                        (LearningCategory.CTA, ["cta", "call to action"]),
                        (LearningCategory.PACKAGING, ["thumbnail", "title", "caption"]),
                    ]),
                    durability=LearningDurability.EXPERIMENTAL,
                    observation=item,
                    implication="This pattern should be validated with more data before becoming durable.",
                    guidance=f"Continue testing variations of: {item}",
                    source_video_ids=[video_id],
                    source_metrics=dict(analysis.metrics or {}),
                    created_at=now,
                    updated_at=now,
                    platform=platform,
                )
            )

        # Extract what failed learnings
        for item in (analysis.what_failed or []):
            learnings.append(
                PerformanceLearning(
                    category=self._categorize_from_text(item, categories_guess=[
                        (LearningCategory.HOOK, ["hook", "opening"]),
                        (LearningCategory.Framing, ["framing", "angle"]),
                        (LearningCategory.AUDIENCE, ["audience"]),
                        (LearningCategory.PROOF, ["proof", "evidence"]),
                        (LearningCategory.FORMAT, ["format", "length"]),
                        (LearningCategory.PACING, ["pacing", "retention"]),
                        (LearningCategory.CTA, ["cta"]),
                        (LearningCategory.PACKAGING, ["thumbnail", "title", "caption"]),
                    ]),
                    durability=LearningDurability.EXPERIMENTAL,
                    observation=item,
                    implication="This pattern should be avoided or significantly modified in future content.",
                    guidance=f"Avoid or change: {item}",
                    source_video_ids=[video_id],
                    source_metrics=dict(analysis.metrics or {}),
                    created_at=now,
                    updated_at=now,
                    platform=platform,
                )
            )

        # Extract audience signals
        for signal in (analysis.audience_signals or []):
            learnings.append(
                PerformanceLearning(
                    category=LearningCategory.AUDIENCE,
                    durability=LearningDurability.EXPERIMENTAL,
                    observation=signal,
                    implication="Audience responded distinctly to this signal.",
                    guidance=f"Explore more content around: {signal}",
                    source_video_ids=[video_id],
                    source_metrics=dict(analysis.metrics or {}),
                    created_at=now,
                    updated_at=now,
                    platform=platform,
                )
            )

        # Extract dropoff hypotheses as pacing/retention learnings
        for hypothesis in (analysis.dropoff_hypotheses or []):
            learnings.append(
                PerformanceLearning(
                    category=LearningCategory.PACING,
                    durability=LearningDurability.EXPERIMENTAL,
                    observation=hypothesis,
                    implication="Retention dropped at this point; structural issue likely.",
                    guidance=f"Address pacing issue: {hypothesis}",
                    source_video_ids=[video_id],
                    source_metrics=dict(analysis.metrics or {}),
                    created_at=now,
                    updated_at=now,
                    platform=platform,
                )
            )

        # Store learnings
        existing = self.load_raw_learnings()
        existing.extend(learnings)
        self.save_raw_learnings(existing)

        return PerformanceLearningSet(video_id=video_id, learnings=learnings, source_analysis=analysis)

    def _categorize_from_text(
        self,
        text: str,
        categories_guess: list[tuple[LearningCategory, list[str]]],
    ) -> LearningCategory:
        """Infer learning category from text content."""
        text_lower = text.lower()
        for category, keywords in categories_guess:
            if any(kw in text_lower for kw in keywords):
                return category
        return LearningCategory.Framing

    def _infer_durability(self, observation: str, metrics: dict[str, Any]) -> LearningDurability:
        """Infer whether a learning is likely durable based on performance strength."""
        # Strong positive signals suggest durability
        views = metrics.get("views", 0) or metrics.get("impressions", 0)
        engagement_rate = metrics.get("engagement_rate", 0) or metrics.get("likes_per_view", 0)

        if views > 10000 and engagement_rate > 0.05:
            return LearningDurability.DURABLE
        if views > 1000 and engagement_rate > 0.03:
            return LearningDurability.EXPERIMENTAL
        return LearningDurability.EXPERIMENTAL

    def _derive_hook_guidance(self, diagnosis: str) -> str:
        """Derive actionable hook guidance from a diagnosis."""
        diagnosis_lower = diagnosis.lower()
        if "strong" in diagnosis_lower or "worked" in diagnosis_lower:
            return "Continue using this hook pattern as the default opening."
        if "weak" in diagnosis_lower or "failed" in diagnosis_lower:
            return "Replace this hook pattern; test alternatives."
        if "average" in diagnosis_lower or "okay" in diagnosis_lower:
            return "Test minor variations on this hook pattern."
        return f"Review and potentially refine: {diagnosis[:100]}"

    # ---------------------------------------------------------------------------
    # Applying learnings to strategy
    # ---------------------------------------------------------------------------

    def apply_learnings_to_strategy(
        self,
        learning_ids: list[str],
        *,
        operator_approved: bool = True,
    ) -> StrategyPerformanceGuidance:
        """Apply selected learnings as durable strategy guidance.

        This is a controlled, operator-visible path. Only learnings that have
        been explicitly selected and approved become durable strategy guidance.

        Args:
            learning_ids: IDs of learnings to promote to strategy guidance
            operator_approved: Whether an operator has explicitly approved this promotion

        Returns:
            The updated strategy guidance
        """
        # Fetch all learnings first to avoid double lookups
        fetched_learnings = [self._get_learning(lid) for lid in learning_ids]
        valid_learnings: list[PerformanceLearning] = []

        for learning in fetched_learnings:
            if learning is None:
                continue
            if not operator_approved and learning.durability != LearningDurability.EXPERIMENTAL:
                continue
            valid_learnings.append(learning)

        guidance = self.load_strategy_guidance()
        guidance = self._merge_learnings_into_guidance(guidance, valid_learnings)
        self.save_strategy_guidance(guidance)

        # Mark learnings as promoted
        for learning in valid_learnings:
            learning.is_active = False  # Superseded by strategy guidance
            learning.updated_at = _now_iso()
        self._save_learnings(valid_learnings)

        return guidance

    def _get_learning(self, learning_id: str) -> PerformanceLearning | None:
        """Get a learning by ID."""
        learnings = self.load_raw_learnings()
        return next((learning for learning in learnings if learning.learning_id == learning_id), None)

    def _save_learnings(self, learnings: list[PerformanceLearning]) -> None:
        """Save updated learnings list."""
        existing = self.load_raw_learnings()
        # Replace updated learnings
        updated_map = {learning.learning_id: learning for learning in learnings}
        merged = [updated_map.get(learning.learning_id, learning) for learning in existing]
        self.save_raw_learnings(merged)

    def _merge_learnings_into_guidance(
        self,
        guidance: StrategyPerformanceGuidance,
        learnings: list[PerformanceLearning],
    ) -> StrategyPerformanceGuidance:
        """Merge learnings into strategy guidance using additive updates."""
        updates: dict[str, list[str]] = {
            "winning_hooks": [],
            "failed_hooks": [],
            "winning_framings": [],
            "failed_framings": [],
            "audience_resonance_notes": [],
            "proof_expectations": [],
            "pending_tests": [],
        }

        for learning in learnings:
            text = learning.guidance or learning.observation
            if not text:
                continue

            if learning.category == LearningCategory.HOOK:
                if "continue" in learning.guidance.lower() or "winning" in learning.observation.lower():
                    if text not in guidance.winning_hooks:
                        updates["winning_hooks"].append(text)
                elif "avoid" in learning.guidance.lower() or "failed" in learning.observation.lower():
                    if text not in guidance.failed_hooks:
                        updates["failed_hooks"].append(text)
            elif learning.category == LearningCategory.FRAMING:
                if "continue" in learning.guidance.lower() or "winning" in learning.observation.lower():
                    if text not in guidance.winning_framings:
                        updates["winning_framings"].append(text)
                elif "avoid" in learning.guidance.lower() or "failed" in learning.observation.lower():
                    if text not in guidance.failed_framings:
                        updates["failed_framings"].append(text)
            elif learning.category == LearningCategory.AUDIENCE:
                if text not in guidance.audience_resonance_notes:
                    updates["audience_resonance_notes"].append(text)
            elif learning.category == LearningCategory.PROOF:
                if text not in guidance.proof_expectations:
                    updates["proof_expectations"].append(text)
            elif learning.category == LearningCategory.PACING:
                if "test" in learning.guidance.lower():
                    if text not in guidance.pending_tests:
                        updates["pending_tests"].append(text)

        # Apply updates as additive
        patch = {k: getattr(guidance, k, []) + v for k, v in updates.items() if v}
        return guidance.model_copy(update=patch)

    # ---------------------------------------------------------------------------
    # Querying learnings
    # ---------------------------------------------------------------------------

    def get_active_learnings(
        self,
        *,
        category: LearningCategory | None = None,
        durability: LearningDurability | None = None,
        platform: str = "",
    ) -> list[PerformanceLearning]:
        """Query learnings by optional filters."""
        learnings = self.load_raw_learnings()
        results = [learning for learning in learnings if learning.is_active]

        if category is not None:
            results = [learning for learning in results if learning.category == category]
        if durability is not None:
            results = [learning for learning in results if learning.durability == durability]
        if platform:
            results = [learning for learning in results if not learning.platform or learning.platform == platform]

        return results

    def get_durable_guidance_for_backlog(
        self,
        *,
        platform: str = "",
    ) -> dict[str, Any]:
        """Get learnings formatted for use in backlog scoring.

        Returns a dict that can be passed to backlog scoring to influence
        idea ranking based on performance history.
        """
        guidance = self.load_strategy_guidance()
        learnings = self.get_active_learnings(
            durability=LearningDurability.DURABLE,
            platform=platform,
        )

        # Build scoring hints from guidance
        hints: dict[str, Any] = {
            "winning_hooks": list(guidance.winning_hooks),
            "failed_hooks": list(guidance.failed_hooks),
            "winning_framings": list(guidance.winning_framings),
            "failed_framings": list(guidance.failed_framings),
            "audience_resonance": list(guidance.audience_resonance_notes),
            "proof_expectations": list(guidance.proof_expectations),
        }

        # Add experimental learnings as hints (not hard rules)
        experimental = self.get_active_learnings(
            durability=LearningDurability.EXPERIMENTAL,
            platform=platform,
        )
        if experimental:
            hints["experimental_learnings"] = [
                {"observation": learning.observation, "guidance": learning.guidance}
                for learning in experimental[:5]  # Limit to 5 most recent
            ]

        return hints
