"""YAML persistence for backlog items."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from cc_deep_research.content_gen.models import BacklogItem, BacklogOutput
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

if TYPE_CHECKING:
    from cc_deep_research.config import Config


class BacklogStore:
    """Load and save :class:`BacklogOutput` to a YAML file."""

    def __init__(self, path: Path | None = None, *, config: "Config | None" = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="backlog_path",
            default_name="backlog.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> BacklogOutput:
        """Load backlog from disk, returning a blank model when missing."""
        if not self._path.exists():
            return BacklogOutput()
        data = yaml.safe_load(self._path.read_text()) or {}
        return BacklogOutput.model_validate(data)

    def save(self, backlog: BacklogOutput) -> None:
        """Persist backlog to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = backlog.model_dump(exclude_none=True)
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def update_item(self, idea_id: str, patch: dict) -> BacklogItem | None:
        """Update a single item and save. Returns the updated item or None."""
        backlog = self.load()
        for item in backlog.items:
            if item.idea_id == idea_id:
                updated = item.model_copy(update=patch)
                backlog.items = [updated if i.idea_id == idea_id else i for i in backlog.items]
                self.save(backlog)
                return updated
        return None
