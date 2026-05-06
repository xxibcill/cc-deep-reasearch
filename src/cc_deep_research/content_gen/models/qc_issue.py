"""QC issue tracking models for structured quality feedback."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .shared import QCIssueCategory, QCIssueSeverity, QCIssueStatus


class QCIssue(BaseModel):
    """A structured QC issue attached to a content-gen output.

    Tracks a specific quality problem found during review, with full
    lifecycle: open → in_review → resolved/dismissed.
    """

    issue_id: str = Field(default_factory=lambda: f"qci_{uuid4().hex[:8]}")
    category: QCIssueCategory = QCIssueCategory.CLARITY_ISSUE
    severity: QCIssueSeverity = QCIssueSeverity.MEDIUM
    status: QCIssueStatus = QCIssueStatus.OPEN

    # What the issue is
    description: str = ""
    affected_beat_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)

    # Provenance - what output this is attached to
    idea_id: str = ""
    brief_id: str = ""
    stage_trace_id: str = ""
    publish_item_id: str = ""

    # Ownership
    owner: str = ""

    # Review tracking
    reviewed_at: str = ""
    reviewed_by: str = ""

    # Resolution
    resolution_note: str = ""
    resolved_at: str = ""
    resolved_by: str = ""

    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    # Additional context
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_blocking(self) -> bool:
        """Return True if this issue blocks publication."""
        return self.severity == QCIssueSeverity.CRITICAL and self.status != QCIssueStatus.RESOLVED

    @property
    def is_open(self) -> bool:
        return self.status == QCIssueStatus.OPEN

    @property
    def is_resolved(self) -> bool:
        return self.status == QCIssueStatus.RESOLVED


class QCIssueReviewHistoryEntry(BaseModel):
    """A single entry in the review history of a QC issue."""

    entry_id: str = Field(default_factory=lambda: f"qcir_{uuid4().hex[:8]}")
    issue_id: str = ""
    action: str = ""  # e.g., "created", "status_changed", "note_added", "resolved"
    actor: str = ""
    note: str = ""
    old_status: QCIssueStatus | None = None
    new_status: QCIssueStatus | None = None
    created_at: str = ""


# Import uuid at runtime to avoid top-level import issues in this module
from uuid import uuid4  # noqa: E402
