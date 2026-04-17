"""YAML persistence for strategy memory."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import (
    RuleChangeOperation,
    RuleVersion,
    RuleVersionKind,
    StrategyMemory,
)
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge patch into base, merging nested dicts rather than replacing them."""
    result: dict[str, Any] = dict(base)
    for key, value in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _model_to_dict(model: Any) -> dict[str, Any]:
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


class StrategyStore:
    """Load and save :class:`StrategyMemory` to a YAML file."""

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="strategy_path",
            default_name="strategy.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> StrategyMemory:
        """Load strategy from disk, returning a blank model when missing."""
        if not self._path.exists():
            return StrategyMemory()
        data = yaml.safe_load(self._path.read_text()) or {}
        return StrategyMemory.model_validate(data)

    def save(self, memory: StrategyMemory) -> None:
        """Persist strategy memory to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = _model_to_dict(memory)
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def update(self, patch: dict[str, Any]) -> StrategyMemory:
        """Load, apply a deep-merged partial update, save, and return the result."""
        memory = self.load()
        merged = _deep_merge(memory.model_dump(), patch)
        updated = StrategyMemory.model_validate(merged)
        self.save(updated)
        return updated

    # ---------------------------------------------------------------------------
    # P7-T2: Rule Version History
    # ---------------------------------------------------------------------------

    def record_rule_version(
        self,
        kind: RuleVersionKind | str,
        operation: RuleChangeOperation | str,
        change_summary: str,
        *,
        previous_value: str = "",
        new_value: str = "",
        source_learning_ids: list[str] | None = None,
        source_content_ids: list[str] | None = None,
        approved_by: str = "",
    ) -> RuleVersion:
        """Record a new rule version in the strategy memory.

        P7-T2: Records versioned rule changes so operators can see when
        guidance changed. Each version records what changed, when, and why.

        Args:
            kind: What kind of rule was changed (hook, framing, scoring, etc.)
            operation: How the rule was changed (added, updated, removed)
            change_summary: Human-readable description of the change
            previous_value: The rule content before change (empty for ADDED)
            new_value: The rule content after change (empty for REMOVED)
            source_learning_ids: Learning IDs that prompted this change
            source_content_ids: Content IDs that provided evidence
            approved_by: Operator who approved (empty if auto-approved)

        Returns:
            The created RuleVersion
        """
        # Normalize string inputs to enums
        if isinstance(kind, str):
            kind = RuleVersionKind(kind)
        if isinstance(operation, str):
            operation = RuleChangeOperation(operation)

        version = RuleVersion(
            kind=kind,
            operation=operation,
            change_summary=change_summary,
            previous_value=previous_value,
            new_value=new_value,
            source_learning_ids=source_learning_ids or [],
            source_content_ids=source_content_ids or [],
            approved_by=approved_by,
            created_at=_now_iso(),
        )

        memory = self.load()
        memory.rule_version_history.versions.append(version)
        self.save(memory)
        return version

    def get_rule_versions(
        self,
        kind: RuleVersionKind | None = None,
    ) -> list[RuleVersion]:
        """Get rule version history, optionally filtered by kind."""
        memory = self.load()
        versions = memory.rule_version_history.versions
        if kind is not None:
            versions = [v for v in versions if v.kind == kind]
        return sorted(versions, key=lambda v: v.created_at)
