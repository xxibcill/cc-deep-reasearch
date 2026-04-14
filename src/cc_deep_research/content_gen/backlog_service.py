"""Managed backlog persistence and lifecycle helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.models import BacklogItem, BacklogOutput, ScoringOutput
from cc_deep_research.content_gen.storage import (
    AuditActor,
    AuditEventType,
    AuditStore,
    BacklogStore,
    SqliteBacklogStore,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class BacklogService:
    """Coordinate backlog persistence, scoring metadata, and status transitions."""

    def __init__(
        self,
        config: Config | None = None,
        store: BacklogStore | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        if store is not None:
            self._store = store
        else:
            use_sqlite = getattr(getattr(config, "content_gen", None), "use_sqlite", False)
            path: Path | None = None
            configured_path = getattr(getattr(config, "content_gen", None), "backlog_path", None)
            if configured_path:
                path = Path(configured_path).expanduser()

            if use_sqlite:
                self._store = SqliteBacklogStore(path)
            else:
                self._store = BacklogStore(path)

        self._audit_store = audit_store

    def set_audit_store(self, audit_store: AuditStore) -> None:
        """Attach an audit store for governance tracking."""
        self._audit_store = audit_store

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
        self._audit_mutation(
            AuditEventType.ITEM_SELECTED,
            idea_id,
            actor=AuditActor.OPERATOR,
            patch={"reason": reason},
            item_snapshot=selected,
            outcome="success",
        )
        return selected

    def update_item(self, idea_id: str, patch: dict[str, Any]) -> BacklogItem | None:
        """Apply a partial item update with timestamp management."""
        if patch.get("status") == "selected":
            reason = patch.get("selection_reasoning")
            return self.select_item(idea_id, reason=str(reason or ""))

        # Capture pre-mutation snapshot for audit
        backlog = self.load()
        pre_item = next((item for item in backlog.items if item.idea_id == idea_id), None)

        normalized_patch = dict(patch)
        normalized_patch["updated_at"] = _now_iso()
        updated = self._store.update_item(idea_id, normalized_patch)
        if updated is not None:
            self._audit_mutation(
                AuditEventType.ITEM_UPDATED,
                idea_id,
                actor=AuditActor.OPERATOR,
                patch=patch,
                item_snapshot=updated,
                outcome="success",
            )
        return updated

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
        item = self.update_item(idea_id, patch)
        if item is not None:
            self._audit_mutation(
                AuditEventType.ITEM_STATUS_CHANGED,
                idea_id,
                actor=AuditActor.OPERATOR,
                patch={"status": "in_production", "source_pipeline_id": source_pipeline_id},
                item_snapshot=item,
                outcome="success",
            )
        return item

    def mark_published(
        self,
        idea_id: str,
        *,
        source_pipeline_id: str = "",
    ) -> BacklogItem | None:
        patch: dict[str, Any] = {"status": "published"}
        if source_pipeline_id:
            patch["source_pipeline_id"] = source_pipeline_id
        item = self.update_item(idea_id, patch)
        if item is not None:
            self._audit_mutation(
                AuditEventType.ITEM_STATUS_CHANGED,
                idea_id,
                actor=AuditActor.OPERATOR,
                patch={"status": "published", "source_pipeline_id": source_pipeline_id},
                item_snapshot=item,
                outcome="success",
            )
        return item

    def _audit_mutation(
        self,
        event_type: AuditEventType,
        idea_id: str,
        actor: AuditActor = AuditActor.OPERATOR,
        patch: dict[str, Any] | None = None,
        item_snapshot: BacklogItem | None = None,
        outcome: str = "success",
    ) -> None:
        """Log a backlog mutation to audit store if configured."""
        if self._audit_store is None:
            return
        self._audit_store.log_backlog_mutation(
            event_type=event_type,
            idea_id=idea_id,
            actor=actor,
            patch=patch,
            item_snapshot=item_snapshot,
            outcome=outcome,
        )

    def create_item(
        self,
        *,
        title: str = "",
        one_line_summary: str = "",
        raw_idea: str = "",
        constraints: str = "",
        idea: str = "",
        category: str = "",
        audience: str = "",
        persona_detail: str = "",
        problem: str = "",
        emotional_driver: str = "",
        urgency_level: str = "",
        source: str = "",
        why_now: str = "",
        hook: str = "",
        potential_hook: str = "",
        content_type: str = "",
        format_duration: str = "",
        key_message: str = "",
        call_to_action: str = "",
        evidence: str = "",
        proof_gap_note: str = "",
        expertise_reason: str = "",
        genericity_risk: str = "",
        risk_level: str = "medium",
        source_theme: str = "",
        selection_reasoning: str = "",
    ) -> BacklogItem:
        """Create a new backlog item with normalized timestamps."""
        now = _now_iso()
        item = BacklogItem(
            title=title or idea,
            one_line_summary=one_line_summary or title or idea,
            raw_idea=raw_idea,
            constraints=constraints,
            idea=idea or title,
            category=category,
            audience=audience,
            persona_detail=persona_detail,
            problem=problem,
            emotional_driver=emotional_driver,
            urgency_level=urgency_level,
            source=source,
            why_now=why_now,
            hook=hook or potential_hook,
            potential_hook=potential_hook,
            content_type=content_type,
            format_duration=format_duration,
            key_message=key_message,
            call_to_action=call_to_action,
            evidence=evidence,
            proof_gap_note=proof_gap_note,
            expertise_reason=expertise_reason,
            genericity_risk=genericity_risk,
            risk_level=risk_level,
            source_theme=source_theme,
            selection_reasoning=selection_reasoning,
            status="captured" if raw_idea and not (title or idea) else "backlog",
            created_at=now,
            updated_at=now,
        )
        backlog = self.load()
        backlog.items.append(item)
        self._store.save(backlog)
        self._audit_mutation(
            AuditEventType.ITEM_CREATED,
            item.idea_id,
            actor=AuditActor.OPERATOR,
            item_snapshot=item,
            outcome="success",
        )
        return item

    def delete_item(self, idea_id: str) -> bool:
        backlog = self.load()
        deleted_item = next((item for item in backlog.items if item.idea_id == idea_id), None)
        filtered_items = [item for item in backlog.items if item.idea_id != idea_id]
        if len(filtered_items) == len(backlog.items):
            return False
        self._store.save(backlog.model_copy(update={"items": filtered_items}))
        if deleted_item is not None:
            self._audit_mutation(
                AuditEventType.ITEM_DELETED,
                idea_id,
                actor=AuditActor.OPERATOR,
                item_snapshot=deleted_item,
                outcome="success",
            )
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
    "captured": 0,
    "backlog": 1,
    "runner_up": 2,
    "selected": 3,
    "in_production": 4,
    "published": 5,
    "archived": 6,
}


def _merge_backlog_status(current_status: str, desired_status: str) -> str:
    if current_status in {"in_production", "published", "archived"}:
        current_rank = _STATUS_PRECEDENCE.get(current_status, 0)
        desired_rank = _STATUS_PRECEDENCE.get(desired_status, 0)
        return current_status if current_rank > desired_rank else desired_status
    return desired_status
