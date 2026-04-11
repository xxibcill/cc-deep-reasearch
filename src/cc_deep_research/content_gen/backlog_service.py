"""Managed backlog persistence and lifecycle helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.models import BacklogItem, BacklogOutput, ScoringOutput
from cc_deep_research.content_gen.storage import BacklogStore

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class BacklogService:
    """Coordinate backlog persistence, scoring metadata, and status transitions."""

    def __init__(self, config: Config | None = None, store: BacklogStore | None = None) -> None:
        if store is not None:
            self._store = store
            return

        path: Path | None = None
        configured_path = getattr(getattr(config, "content_gen", None), "backlog_path", None)
        if configured_path:
            path = Path(configured_path).expanduser()
        self._store = BacklogStore(path)

    @property
    def path(self) -> Path:
        return self._store.path

    def load(self) -> BacklogOutput:
        return self._store.load()

    def persist_generated(
        self,
        backlog: BacklogOutput,
        *,
        theme: str = "",
        source_pipeline_id: str = "",
    ) -> BacklogOutput:
        """Persist generated backlog items and return the normalized stage output."""
        persisted_items = self.upsert_items(
            backlog.items,
            theme=theme,
            source_pipeline_id=source_pipeline_id,
        )
        return backlog.model_copy(update={"items": persisted_items})

    def upsert_items(
        self,
        items: list[BacklogItem],
        *,
        theme: str = "",
        source_pipeline_id: str = "",
    ) -> list[BacklogItem]:
        """Insert or update items while preserving operator-managed metadata."""
        backlog = self.load()
        persisted_items, merged_items = self._merge_items(
            backlog.items,
            items,
            theme=theme,
            source_pipeline_id=source_pipeline_id,
        )
        self._store.save(backlog.model_copy(update={"items": merged_items}))
        return persisted_items

    def apply_scoring(self, scoring: ScoringOutput) -> BacklogOutput:
        """Attach latest scoring metadata to persisted backlog items."""
        backlog = self.load()
        if not backlog.items:
            return backlog

        now = _now_iso()
        score_by_id = {score.idea_id: score for score in scoring.scores}
        active_runner_up_ids = {
            candidate.idea_id
            for candidate in scoring.active_candidates
            if candidate.role == "runner_up"
        }
        updated_items: list[BacklogItem] = []

        for item in backlog.items:
            patch: dict[str, Any] = {}
            score = score_by_id.get(item.idea_id)
            if score is not None:
                patch["latest_score"] = score.total_score
                patch["latest_recommendation"] = score.recommendation
                patch["last_scored_at"] = now

            if scoring.selected_idea_id and item.idea_id == scoring.selected_idea_id:
                patch["status"] = _merge_backlog_status(item.status, "selected")
                patch["selection_reasoning"] = scoring.selection_reasoning
            elif item.idea_id in active_runner_up_ids:
                patch["status"] = _merge_backlog_status(item.status, "runner_up")
                patch["selection_reasoning"] = ""
            elif item.status in {"selected", "runner_up"}:
                patch["status"] = "backlog"
                patch["selection_reasoning"] = ""

            if patch:
                patch["updated_at"] = now
                item = item.model_copy(update=patch)
            updated_items.append(item)

        updated = backlog.model_copy(update={"items": updated_items})
        self._store.save(updated)
        return updated

    def select_item(self, idea_id: str, *, reason: str = "") -> BacklogItem | None:
        """Select one backlog item and clear previous selections."""
        backlog = self.load()
        now = _now_iso()
        selected: BacklogItem | None = None
        updated_items: list[BacklogItem] = []

        for item in backlog.items:
            if item.idea_id == idea_id:
                item = item.model_copy(
                    update={
                        "status": "selected",
                        "selection_reasoning": reason or item.selection_reasoning,
                        "updated_at": now,
                    }
                )
                selected = item
            elif item.status == "selected":
                item = item.model_copy(
                    update={
                        "status": "backlog",
                        "selection_reasoning": "",
                        "updated_at": now,
                    }
                )
            updated_items.append(item)

        if selected is None:
            return None

        self._store.save(backlog.model_copy(update={"items": updated_items}))
        return selected

    def update_item(self, idea_id: str, patch: dict[str, Any]) -> BacklogItem | None:
        """Apply a partial item update with timestamp management."""
        if patch.get("status") == "selected":
            reason = patch.get("selection_reasoning")
            return self.select_item(idea_id, reason=str(reason or ""))

        normalized_patch = dict(patch)
        normalized_patch["updated_at"] = _now_iso()
        return self._store.update_item(idea_id, normalized_patch)

    def archive_item(self, idea_id: str) -> BacklogItem | None:
        return self.update_item(idea_id, {"status": "archived"})

    def mark_in_production(
        self,
        idea_id: str,
        *,
        source_pipeline_id: str = "",
    ) -> BacklogItem | None:
        patch: dict[str, Any] = {"status": "in_production"}
        if source_pipeline_id:
            patch["source_pipeline_id"] = source_pipeline_id
        return self.update_item(idea_id, patch)

    def mark_published(
        self,
        idea_id: str,
        *,
        source_pipeline_id: str = "",
    ) -> BacklogItem | None:
        patch: dict[str, Any] = {"status": "published"}
        if source_pipeline_id:
            patch["source_pipeline_id"] = source_pipeline_id
        return self.update_item(idea_id, patch)

    def delete_item(self, idea_id: str) -> bool:
        backlog = self.load()
        filtered_items = [item for item in backlog.items if item.idea_id != idea_id]
        if len(filtered_items) == len(backlog.items):
            return False
        self._store.save(backlog.model_copy(update={"items": filtered_items}))
        return True

    @staticmethod
    def _merge_items(
        existing_items: list[BacklogItem],
        new_items: list[BacklogItem],
        *,
        theme: str = "",
        source_pipeline_id: str = "",
    ) -> tuple[list[BacklogItem], list[BacklogItem]]:
        now = _now_iso()
        merged_items = list(existing_items)
        existing_index = {item.idea_id: idx for idx, item in enumerate(merged_items)}
        persisted_items: list[BacklogItem] = []

        for item in new_items:
            existing = merged_items[existing_index[item.idea_id]] if item.idea_id in existing_index else None

            status = item.status
            if existing is not None and status == "backlog":
                status = existing.status

            persisted = item.model_copy(
                update={
                    "status": status or "backlog",
                    "latest_score": item.latest_score if item.latest_score is not None else getattr(existing, "latest_score", None),
                    "latest_recommendation": item.latest_recommendation or getattr(existing, "latest_recommendation", ""),
                    "selection_reasoning": item.selection_reasoning or getattr(existing, "selection_reasoning", ""),
                    "source_theme": item.source_theme or getattr(existing, "source_theme", "") or theme,
                    "source_pipeline_id": item.source_pipeline_id or getattr(existing, "source_pipeline_id", "") or source_pipeline_id,
                    "created_at": getattr(existing, "created_at", "") or now,
                    "updated_at": now,
                    "last_scored_at": item.last_scored_at or getattr(existing, "last_scored_at", ""),
                }
            )

            if existing is None:
                existing_index[persisted.idea_id] = len(merged_items)
                merged_items.append(persisted)
            else:
                merged_items[existing_index[persisted.idea_id]] = persisted
            persisted_items.append(persisted)

        return persisted_items, merged_items


_STATUS_PRECEDENCE = {
    "backlog": 0,
    "runner_up": 1,
    "selected": 2,
    "in_production": 3,
    "published": 4,
    "archived": 5,
}


def _merge_backlog_status(current_status: str, desired_status: str) -> str:
    if current_status in {"in_production", "published", "archived"}:
        current_rank = _STATUS_PRECEDENCE.get(current_status, 0)
        desired_rank = _STATUS_PRECEDENCE.get(desired_status, 0)
        return current_status if current_rank > desired_rank else desired_status
    return desired_status
