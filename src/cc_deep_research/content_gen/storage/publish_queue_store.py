"""YAML persistence for the publish queue."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from cc_deep_research.content_gen.models import PublishItem
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

if TYPE_CHECKING:
    from cc_deep_research.config import Config


class PublishQueueStore:
    """Load and save publish queue entries to a YAML file."""

    def __init__(self, path: Path | None = None, *, config: "Config | None" = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="publish_queue_path",
            default_name="publish_queue.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[PublishItem]:
        """Load queue from disk, returning an empty list when missing."""
        if not self._path.exists():
            return []
        data = yaml.safe_load(self._path.read_text()) or {}
        items = data.get("items", [])
        return [PublishItem.model_validate(i) for i in items]

    def save(self, items: list[PublishItem]) -> None:
        """Persist publish queue to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": [i.model_dump(exclude_none=True) for i in items]}
        self._path.write_text(yaml.dump(payload, default_flow_style=False, sort_keys=False))

    def add(self, item: PublishItem) -> list[PublishItem]:
        """Append an item and save."""
        items = self.load()
        items.append(item)
        self.save(items)
        return items

    def update_status(self, idea_id: str, platform: str, status: str) -> PublishItem | None:
        """Update status for a queued item. Returns the item or None."""
        items = self.load()
        for item in items:
            if item.idea_id == idea_id and item.platform == platform:
                item = item.model_copy(update={"status": status})
                items = [
                    item if (i.idea_id == idea_id and i.platform == platform) else i for i in items
                ]
                self.save(items)
                return item
        return None
