"""Route-facing API service for strategy HTTP workflows.

This service handles HTTP-level composition (request parsing, response shaping,
error classification) while delegating domain behavior to StrategyStore and
PerformanceLearningStore.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.models.angle import StrategyMemory
from cc_deep_research.content_gen.models.brief import StrategyReadinessResult
from cc_deep_research.content_gen.models.learning import RuleVersion
from cc_deep_research.content_gen.models.shared import (
    LearningCategory,
    LearningDurability,
    RuleLifecycleStatus,
)
from cc_deep_research.content_gen.storage import PerformanceLearningStore
from cc_deep_research.content_gen.storage.strategy_store import StrategyStore

if TYPE_CHECKING:
    from cc_deep_research.config import Config


logger = logging.getLogger(__name__)


class StrategyApiError(Exception):
    """Base class for strategy API errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class RuleVersionNotFoundError(StrategyApiError):
    """Raised when a rule version does not exist."""

    def __init__(self, version_id: str) -> None:
        super().__init__(f"Rule version not found: {version_id}", status_code=404)


class LearningNotFoundError(StrategyApiError):
    """Raised when a learning does not exist."""

    def __init__(self, learning_ids: list[str]) -> None:
        super().__init__(f"Learnings not found: {', '.join(learning_ids)}", status_code=404)


class StrategyApiService:
    """API-level service for strategy HTTP request handling.

    This class handles HTTP-specific concerns:
    - Request validation and parsing
    - Response shaping (serialization)
    - Error classification and mapping

    Domain behavior is delegated to StrategyStore and PerformanceLearningStore.
    """

    def __init__(
        self,
        config: Config | None = None,
        strategy_store: StrategyStore | None = None,
        learning_store: PerformanceLearningStore | None = None,
    ) -> None:
        self._config = config
        self._strategy_store = strategy_store or StrategyStore(config=config)
        self._learning_store = learning_store or PerformanceLearningStore()

    @property
    def path(self) -> Path:
        """Return the strategy store path."""
        return self._strategy_store.path

    # ------------------------------------------------------------------
    # Strategy memory
    # ------------------------------------------------------------------

    def get_strategy(self) -> StrategyMemory:
        """Get the current strategy memory.

        Returns:
            StrategyMemory object.
        """
        return self._strategy_store.load()

    def update_strategy(self, patch: dict[str, Any]) -> StrategyMemory:
        """Update strategy memory with a deep-merged patch.

        Args:
            patch: Fields to update in the strategy memory.

        Returns:
            Updated StrategyMemory object.
        """
        return self._strategy_store.update(patch)

    # ------------------------------------------------------------------
    # Strategy readiness
    # ------------------------------------------------------------------

    def check_readiness(self) -> StrategyReadinessResult:
        """Check strategy readiness and return validation results.

        Returns:
            StrategyReadinessResult with readiness level, issues, and summary.
        """
        return self._strategy_store.check_readiness()

    # ------------------------------------------------------------------
    # Rule governance
    # ------------------------------------------------------------------

    def get_rules_for_review(self) -> list[RuleVersion]:
        """Get all rules that need operator review.

        Returns:
            List of RuleVersion objects needing review.
        """
        return self._strategy_store.get_rules_for_review()

    def update_rule_lifecycle(
        self,
        version_id: str,
        status: str | None = None,
        confidence: float | None = None,
        evidence_count: int | None = None,
        review_after: str | None = None,
        review_notes: str | None = None,
    ) -> RuleVersion:
        """Update lifecycle metadata for a rule version.

        Args:
            version_id: ID of the rule version to update.
            status: New lifecycle status.
            confidence: Updated confidence score.
            evidence_count: Updated evidence count.
            review_after: ISO date string for next review date.
            review_notes: Operator review notes.

        Returns:
            Updated RuleVersion.

        Raises:
            RuleVersionNotFoundError: If version_id doesn't exist.
        """
        normalized_status = RuleLifecycleStatus(status) if status else None
        version = self._strategy_store.update_rule_lifecycle(
            version_id,
            status=normalized_status,
            confidence=confidence,
            evidence_count=evidence_count,
            review_after=review_after,
            review_notes=review_notes,
        )
        if version is None:
            raise RuleVersionNotFoundError(version_id)
        return version

    # ------------------------------------------------------------------
    # Performance learnings
    # ------------------------------------------------------------------

    def list_learnings(
        self,
        category: str | None = None,
        durability: str | None = None,
    ) -> tuple[list[Any], int]:
        """List active performance learnings with optional filtering.

        Args:
            category: Optional learning category filter.
            durability: Optional durability filter.

        Returns:
            Tuple of (learnings_list, count).
        """
        category_enum = LearningCategory(category) if category else None
        durability_enum = LearningDurability(durability) if durability else None
        items = self._learning_store.get_active_learnings(
            category=category_enum,
            durability=durability_enum,
        )
        return items, len(items)

    def apply_learnings(
        self,
        learning_ids: list[str],
        operator_approved: bool = True,
    ) -> Any:
        """Promote learnings into strategy rules.

        Args:
            learning_ids: List of learning IDs to apply.
            operator_approved: Whether operator approved this application.

        Returns:
            Guidance result from applying learnings.

        Raises:
            LearningNotFoundError: If any learning_id doesn't exist.
        """
        guidance = self._learning_store.apply_learnings_to_strategy(
            learning_ids,
            operator_approved=operator_approved,
            record_versions=True,
        )
        return guidance

    # ------------------------------------------------------------------
    # Telemetry queries
    # ------------------------------------------------------------------

    def list_rule_versions(self, kind: str | None = None) -> list[dict[str, Any]]:
        """List rule versions from telemetry.

        Args:
            kind: Optional rule kind filter.

        Returns:
            List of rule version records from telemetry.
        """
        from cc_deep_research.telemetry.query import query_content_gen_rule_versions

        return query_content_gen_rule_versions(kind=kind)

    def get_operating_fitness(self) -> dict[str, Any]:
        """Get operating fitness metrics.

        Returns:
            Operating fitness data from telemetry.
        """
        from cc_deep_research.telemetry.query import query_content_gen_operating_fitness

        return query_content_gen_operating_fitness()

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_strategy(memory: StrategyMemory) -> dict[str, Any]:
        """Serialize a StrategyMemory to JSON-compatible dict."""
        return json.loads(memory.model_dump_json())

    @staticmethod
    def serialize_readiness(result: StrategyReadinessResult) -> dict[str, Any]:
        """Serialize a StrategyReadinessResult to JSON-compatible dict."""
        return json.loads(result.model_dump_json())

    @staticmethod
    def serialize_rule_version(version: RuleVersion) -> dict[str, Any]:
        """Serialize a RuleVersion to JSON-compatible dict."""
        return json.loads(version.model_dump_json())

    @staticmethod
    def serialize_learning(item: Any) -> dict[str, Any]:
        """Serialize a learning item to JSON-compatible dict."""
        return json.loads(item.model_dump_json()) if hasattr(item, "model_dump_json") else item
