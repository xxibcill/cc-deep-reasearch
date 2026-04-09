"""YAML persistence for strategy memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from cc_deep_research.content_gen.models import StrategyMemory

_DEFAULT_DIR = Path.home() / ".config" / "cc-deep-research"
_DEFAULT_NAME = "strategy.yaml"


class StrategyStore:
    """Load and save :class:`StrategyMemory` to a YAML file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_DIR / _DEFAULT_NAME

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
        data = memory.model_dump(exclude_none=True)
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def update(self, patch: dict[str, Any]) -> StrategyMemory:
        """Load, apply a partial update, save, and return the result."""
        memory = self.load()
        updated = memory.model_copy(update=patch)
        self.save(updated)
        return updated
