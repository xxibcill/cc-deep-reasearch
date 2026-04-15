"""Append-only audit log for AI proposals, approvals, and backlog mutations.

This module provides an AuditStore that records governance events in an
append-only log file. Each event records the actor, action, payload,
and outcome so operators can later reconstruct why changes were made.

Audit entries are stored in:
~/.config/cc-deep-research/content-gen/audit_log.yaml

The log is append-only: past entries are never modified or deleted,
only new entries are added.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import BacklogItem
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

if TYPE_CHECKING:
    from cc_deep_research.config import Config


class AuditEventType(StrEnum):
    """Types of auditable governance events."""

    # AI-driven proposals (from triage, chat, scoring)
    PROPOSAL_CREATED = "proposal_created"
    PROPOSAL_APPLIED = "proposal_applied"
    PROPOSAL_REJECTED = "proposal_rejected"
    PROPOSAL_EXPIRED = "proposal_expired"

    # Manual operator actions on backlog items
    ITEM_CREATED = "item_created"
    ITEM_UPDATED = "item_updated"
    ITEM_DELETED = "item_deleted"
    ITEM_SELECTED = "item_selected"
    ITEM_ARCHIVED = "item_archived"
    ITEM_STATUS_CHANGED = "item_status_changed"

    # Scoring / selection events
    SCORING_RUN = "scoring_run"
    ITEM_PROMOTED = "item_promoted"
    ITEM_DEMOTED = "item_demoted"

    # Pipeline events
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"

    # Maintenance workflow events
    MAINTENANCE_JOB_RUN = "maintenance_job_run"
    MAINTENANCE_PROPOSAL = "maintenance_proposal"

    # Brief management events
    BRIEF_CREATED = "brief_created"
    BRIEF_UPDATED = "brief_updated"
    BRIEF_REVISION_SAVED = "brief_revision_saved"
    BRIEF_HEAD_UPDATED = "brief_head_updated"
    BRIEF_LIFECYCLE_CHANGED = "brief_lifecycle_changed"


class AuditActor(StrEnum):
    """Who or what initiated the event."""

    OPERATOR = "operator"  # Human operator
    AI_PROPOSAL = "ai_proposal"  # AI-generated proposal (triage, chat)
    SYSTEM = "system"  # Automated system action
    MAINTENANCE = "maintenance"  # Background maintenance job


class AuditEntry:
    """Single append-only audit log entry.

    Attributes
    ----------
    event_id : str
        Unique identifier for this event (UUID prefix).
    event_type : AuditEventType
        What kind of event occurred.
    actor : AuditActor
        Who/what initiated the action.
    actor_label : str
        Human-readable label for the actor (operator name, AI model, etc.).
    idea_id : str
        The backlog idea this event relates to (empty if not item-specific).
    proposal_id : str
        The proposal ID this event relates to (for proposal events).
    pipeline_id : str
        The pipeline ID this event relates to (for pipeline events).
    description : str
        Human-readable description of the event.
    payload : dict
        The full event payload (AI proposal, patch, etc.).
    outcome : str
        Outcome of the action (applied, rejected, failed, etc.).
    timestamp : str
        ISO timestamp of when the event was recorded.
    """

    def __init__(
        self,
        event_type: AuditEventType | str,
        actor: AuditActor | str,
        *,
        actor_label: str = "",
        idea_id: str = "",
        proposal_id: str = "",
        pipeline_id: str = "",
        description: str = "",
        payload: dict[str, Any] | None = None,
        outcome: str = "",
        event_id: str = "",
        timestamp: str = "",
    ) -> None:
        from uuid import uuid4

        self.event_id = event_id or uuid4().hex[:12]
        self.event_type = AuditEventType(event_type) if isinstance(event_type, str) else event_type
        self.actor = AuditActor(actor) if isinstance(actor, str) else actor
        self.actor_label = actor_label
        self.idea_id = idea_id
        self.proposal_id = proposal_id
        self.pipeline_id = pipeline_id
        self.description = description
        self.payload = payload or {}
        self.outcome = outcome
        self.timestamp = timestamp or datetime.now(tz=UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": str(self.event_type.value),
            "actor": str(self.actor.value),
            "actor_label": self.actor_label,
            "idea_id": self.idea_id,
            "proposal_id": self.proposal_id,
            "pipeline_id": self.pipeline_id,
            "description": self.description,
            "payload": self.payload,
            "outcome": self.outcome,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        # Safely parse enum fields, falling back to defaults if invalid
        event_type_str = data.get("event_type", "")
        try:
            event_type = AuditEventType(event_type_str) if event_type_str else AuditEventType.PROPOSAL_CREATED
        except ValueError:
            event_type = AuditEventType.PROPOSAL_CREATED

        actor_str = data.get("actor", "")
        try:
            actor = AuditActor(actor_str) if actor_str else AuditActor.SYSTEM
        except ValueError:
            actor = AuditActor.SYSTEM

        return cls(
            event_id=data.get("event_id", ""),
            event_type=event_type,
            actor=actor,
            actor_label=data.get("actor_label", ""),
            idea_id=data.get("idea_id", ""),
            proposal_id=data.get("proposal_id", ""),
            pipeline_id=data.get("pipeline_id", ""),
            description=data.get("description", ""),
            payload=data.get("payload", {}),
            outcome=data.get("outcome", ""),
            timestamp=data.get("timestamp", ""),
        )


class AuditStore:
    """Append-only audit log persisted to YAML.

    All entries are stored in a single YAML list. New entries are
    appended to the list without modifying existing entries.
    """

    _lock: Any = None  # threading.Lock set in __init__ per subclass

    def __init__(self, path: Any = None, *, config: Config | None = None) -> None:
        import threading

        self._lock = threading.Lock()
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="backlog_path",  # Same directory as backlog
            default_name="audit_log.yaml",
            use_config_parent=path is None,
        )
        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Any:
        return self._path

    def load_entries(
        self,
        *,
        idea_id: str | None = None,
        event_type: AuditEventType | None = None,
        actor: AuditActor | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Load audit entries with optional filtering.

        Parameters
        ----------
        idea_id : str, optional
            Filter to entries for a specific backlog item.
        event_type : AuditEventType, optional
            Filter to a specific event type.
        actor : AuditActor, optional
            Filter to entries from a specific actor type.
        limit : int
            Maximum number of entries to return (most recent first).

        Returns
        -------
        list[AuditEntry]
            Filtered, sorted audit entries (most recent first).
        """
        if not self._path.exists():
            return []

        with self._lock:
            data = yaml.safe_load(self._path.read_text()) or []

        entries = [AuditEntry.from_dict(item) for item in data]

        if idea_id:
            entries = [e for e in entries if e.idea_id == idea_id]
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        if actor:
            entries = [e for e in entries if e.actor == actor]

        # Most recent first
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def append(self, entry: AuditEntry) -> None:
        """Append a new audit entry to the log (thread-safe)."""
        with self._lock:
            data: list[dict[str, Any]] = []
            if self._path.exists():
                data = yaml.safe_load(self._path.read_text()) or []

            data.append(entry.to_dict())
            self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def log_proposal(
        self,
        proposal_id: str,
        idea_ids: list[str],
        actor_label: str,
        payload: dict[str, Any],
        *,
        pipeline_id: str = "",
    ) -> AuditEntry:
        """Record an AI proposal event."""
        entry = AuditEntry(
            event_type=AuditEventType.PROPOSAL_CREATED,
            actor=AuditActor.AI_PROPOSAL,
            actor_label=actor_label,
            proposal_id=proposal_id,
            idea_id=", ".join(idea_ids) if len(idea_ids) == 1 else "",
            pipeline_id=pipeline_id,
            description=f"AI proposal {proposal_id} for {len(idea_ids)} item(s)",
            payload=payload,
            outcome="pending",
        )
        self.append(entry)
        return entry

    def log_proposal_outcome(
        self,
        proposal_id: str,
        idea_ids: list[str],
        outcome: str,
        *,
        actor: AuditActor = AuditActor.OPERATOR,
        actor_label: str = "",
        pipeline_id: str = "",
    ) -> AuditEntry:
        """Record the outcome of a proposal (applied or rejected)."""
        event_type = (
            AuditEventType.PROPOSAL_APPLIED if outcome == "applied" else AuditEventType.PROPOSAL_REJECTED
        )
        entry = AuditEntry(
            event_type=event_type,
            actor=actor,
            actor_label=actor_label,
            proposal_id=proposal_id,
            idea_id=", ".join(idea_ids) if len(idea_ids) == 1 else "",
            pipeline_id=pipeline_id,
            description=f"Proposal {proposal_id} {outcome}",
            payload={"idea_ids": idea_ids, "outcome": outcome},
            outcome=outcome,
        )
        self.append(entry)
        return entry

    def log_backlog_mutation(
        self,
        event_type: AuditEventType,
        idea_id: str,
        actor: AuditActor,
        *,
        actor_label: str = "",
        patch: dict[str, Any] | None = None,
        item_snapshot: BacklogItem | None = None,
        outcome: str = "success",
    ) -> AuditEntry:
        """Record a mutation to a backlog item."""
        snapshot: dict[str, Any] = {}
        if item_snapshot is not None:
            snapshot = item_snapshot.model_dump(exclude_none=True)

        entry = AuditEntry(
            event_type=event_type,
            actor=actor,
            actor_label=actor_label,
            idea_id=idea_id,
            description=f"{event_type.value}: {idea_id}",
            payload={"patch": patch or {}, "item_snapshot": snapshot},
            outcome=outcome,
        )
        self.append(entry)
        return entry
