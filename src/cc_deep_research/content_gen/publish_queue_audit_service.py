"""Route-facing API service for publish queue and audit HTTP workflows.

This service handles HTTP-level composition (request parsing, response shaping,
error classification) while delegating domain behavior to PublishQueueStore
and AuditStore.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.models import PublishItem
from cc_deep_research.content_gen.storage import (
    AuditActor,
    AuditEventType,
    AuditStore,
    PublishQueueStore,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config


logger = logging.getLogger(__name__)


class PublishQueueApiError(Exception):
    """Base class for publish queue API errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuditApiError(Exception):
    """Base class for audit API errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PublishQueueAuditService:
    """API-level service for publish queue and audit HTTP request handling.

    This class handles HTTP-specific concerns:
    - Request validation and parsing
    - Response shaping (serialization)
    - Error classification and mapping

    Domain behavior is delegated to PublishQueueStore and AuditStore.
    """

    def __init__(
        self,
        config: Config | None = None,
        publish_store: PublishQueueStore | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self._config = config
        self._publish_store = publish_store or PublishQueueStore(config=config)
        self._audit_store = audit_store or AuditStore(config=config)

    @property
    def publish_path(self) -> Path:
        """Return the publish queue store path."""
        return self._publish_store.path

    @property
    def audit_path(self) -> Path:
        """Return the audit store path."""
        return self._audit_store.path

    # ------------------------------------------------------------------
    # Publish queue
    # ------------------------------------------------------------------

    def list_publish_queue(self) -> list[PublishItem]:
        """List all items in the publish queue.

        Returns:
            List of PublishItem objects.
        """
        return self._publish_store.load()

    def remove_from_queue(self, idea_id: str, platform: str) -> int:
        """Remove an item from the publish queue.

        Args:
            idea_id: ID of the idea to remove.
            platform: Platform of the item to remove.

        Returns:
            Number of items removed (0 or 1).
        """
        items = self._publish_store.load()
        filtered = [i for i in items if not (i.idea_id == idea_id and i.platform == platform)]
        self._publish_store.save(filtered)
        removed = len(items) - len(filtered)
        return removed

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def list_audit_entries(
        self,
        idea_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        """List audit log entries with optional filtering.

        Args:
            idea_id: Optional filter for a specific backlog item.
            event_type: Optional filter for a specific event type.
            actor: Optional filter for a specific actor.
            limit: Maximum number of entries to return.

        Returns:
            Tuple of (entries_list, count).
        """
        event_type_enum = AuditEventType(event_type) if event_type else None
        actor_enum = AuditActor(actor) if actor else None
        entries = self._audit_store.load_entries(
            idea_id=idea_id,
            event_type=event_type_enum,
            actor=actor_enum,
            limit=limit,
        )
        return [entry.to_dict() for entry in entries], len(entries)

    def get_audit_for_item(
        self,
        idea_id: str,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get audit history for a specific backlog item.

        Args:
            idea_id: ID of the backlog item.
            limit: Maximum number of entries to return.

        Returns:
            Tuple of (entries_list, count).
        """
        entries = self._audit_store.load_entries(idea_id=idea_id, limit=limit)
        return [entry.to_dict() for entry in entries], len(entries)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_publish_item(item: PublishItem) -> dict[str, Any]:
        """Serialize a PublishItem to JSON-compatible dict."""
        return item.model_dump(mode="json")

    @staticmethod
    def serialize_audit_entry(entry: dict[str, Any]) -> dict[str, Any]:
        """Serialize an audit entry dict to JSON-compatible dict."""
        return entry
