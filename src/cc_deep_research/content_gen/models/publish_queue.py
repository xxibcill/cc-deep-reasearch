"""Publish queue blocker and readiness models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .shared import PublishReadinessState


class PublishBlocker(BaseModel):
    """A blocker preventing a publish queue item from advancing.

    Blockers can reference QC issues, missing assets, missing approvals,
    or strategy conflicts. They are resolved by addressing the underlying cause.
    """

    blocker_id: str = Field(default_factory=lambda: f"blk_{uuid4().hex[:8]}")
    blocker_type: str = ""  # "qc_issue", "missing_asset", "missing_approval", "strategy_conflict"
    severity: str = "high"  # "low", "medium", "high", "critical"

    # What is blocked
    idea_id: str = ""
    platform: str = ""

    # What the blocker is
    description: str = ""
    related_issue_ids: list[str] = Field(default_factory=list)
    related_asset_ids: list[str] = Field(default_factory=list)

    # Resolution
    is_resolved: bool = False
    resolution_note: str = ""
    resolved_at: str = ""
    resolved_by: str = ""

    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    # Additional context
    metadata: dict[str, Any] = Field(default_factory=dict)


class PublishQueueReviewEntry(BaseModel):
    """A single review action on a publish queue item."""

    entry_id: str = Field(default_factory=lambda: f"pqre_{uuid4().hex[:8]}")
    idea_id: str = ""
    platform: str = ""

    action: str = ""  # e.g., "submitted_for_review", "approved", "rejected", "scheduled", "note_added"
    actor: str = ""
    note: str = ""

    # State before and after (when applicable)
    old_readiness: PublishReadinessState | None = None
    new_readiness: PublishReadinessState | None = None
    old_status: str | None = None
    new_status: str | None = None

    created_at: str = ""


class PublishQueueOperatorNote(BaseModel):
    """An operator note attached to a publish queue item."""

    note_id: str = Field(default_factory=lambda: f"pqon_{uuid4().hex[:8]}")
    idea_id: str = ""
    platform: str = ""

    content: str = ""
    author: str = ""

    created_at: str = ""
    updated_at: str = ""


# Import uuid at runtime to avoid top-level import issues in this module
from uuid import uuid4  # noqa: E402
