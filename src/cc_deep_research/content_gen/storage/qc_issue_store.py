"""YAML persistence for QC issues."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import (
    QCIssue,
    QCIssueCategory,
    QCIssueReviewHistoryEntry,
    QCIssueSeverity,
    QCIssueStatus,
)
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path
from cc_deep_research.persistence import atomic_write_text

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _serialize_model_to_dict(model: Any) -> dict[str, Any]:
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


class QCIssueStore:
    """Load and save QC issues to a YAML file.

    Provides controlled paths for:
    - Creating and storing structured QC issues
    - Updating issue status and resolution
    - Filtering by category, severity, status, owner
    - Review history tracking
    """

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="qc_issue_path",
            default_name="qc_issues.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[QCIssue]:
        """Load all QC issues from disk."""
        if not self._path.exists():
            return []
        data = yaml.safe_load(self._path.read_text()) or {}
        items = data.get("issues", [])
        return [QCIssue.model_validate(i) for i in items]

    def save(self, issues: list[QCIssue]) -> None:
        """Persist all QC issues to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "issues": [_serialize_model_to_dict(issue) for issue in issues],
            "last_updated": _now_iso(),
        }
        atomic_write_text(
            self._path,
            yaml.dump(payload, default_flow_style=False, sort_keys=False),
        )

    def add(self, issue: QCIssue) -> list[QCIssue]:
        """Append an issue and save. Sets created_at and updated_at if empty."""
        if not issue.created_at:
            issue.created_at = _now_iso()
        if not issue.updated_at:
            issue.updated_at = _now_iso()
        issues = self.load()
        issues.append(issue)
        self.save(issues)
        return issues

    def get(self, issue_id: str) -> QCIssue | None:
        """Get a single issue by ID."""
        issues = self.load()
        return next((issue for issue in issues if issue.issue_id == issue_id), None)

    def update(self, issue_id: str, updates: dict[str, Any]) -> QCIssue | None:
        """Update specific fields of an issue and set updated_at."""
        issues = self.load()
        for i, issue in enumerate(issues):
            if issue.issue_id == issue_id:
                update_data = updates.copy()
                update_data["updated_at"] = _now_iso()
                issues[i] = issue.model_copy(update=update_data)
                self.save(issues)
                return issues[i]
        return None

    def resolve(
        self,
        issue_id: str,
        resolution_note: str,
        resolved_by: str = "operator",
    ) -> QCIssue | None:
        """Mark an issue as resolved."""
        return self.update(
            issue_id,
            {
                "status": QCIssueStatus.RESOLVED,
                "resolution_note": resolution_note,
                "resolved_by": resolved_by,
                "resolved_at": _now_iso(),
            },
        )

    def dismiss(
        self,
        issue_id: str,
        resolution_note: str,
        dismissed_by: str = "operator",
    ) -> QCIssue | None:
        """Dismiss an issue (determined not to be a real problem)."""
        return self.update(
            issue_id,
            {
                "status": QCIssueStatus.DISMISSED,
                "resolution_note": resolution_note,
                "resolved_by": dismissed_by,
                "resolved_at": _now_iso(),
            },
        )

    def filter(
        self,
        *,
        category: QCIssueCategory | None = None,
        severity: QCIssueSeverity | None = None,
        status: QCIssueStatus | None = None,
        owner: str | None = None,
        idea_id: str | None = None,
        brief_id: str | None = None,
    ) -> list[QCIssue]:
        """Filter issues by optional criteria."""
        issues = self.load()
        if category is not None:
            issues = [i for i in issues if i.category == category]
        if severity is not None:
            issues = [i for i in issues if i.severity == severity]
        if status is not None:
            issues = [i for i in issues if i.status == status]
        if owner is not None:
            issues = [i for i in issues if i.owner == owner]
        if idea_id is not None:
            issues = [i for i in issues if i.idea_id == idea_id]
        if brief_id is not None:
            issues = [i for i in issues if i.brief_id == brief_id]
        return issues

    def get_blocking_issues(self, idea_id: str) -> list[QCIssue]:
        """Get all open critical/high severity issues for an idea."""
        return [
            issue
            for issue in self.load()
            if issue.idea_id == idea_id
            and issue.is_blocking
        ]

    def add_review_history_entry(
        self,
        entry: QCIssueReviewHistoryEntry,
    ) -> None:
        """Append a review history entry to the issue."""
        entry.created_at = _now_iso()
        issues = self.load()
        for i, issue in enumerate(issues):
            if issue.issue_id == entry.issue_id:
                # Serialize the entry
                entry_dict = _serialize_model_to_dict(entry)
                # We store review history as JSON-serialized string in metadata
                # to avoid changing the model structure
                history = issue.metadata.get("review_history", [])
                history.append(entry_dict)
                issues[i] = issue.model_copy(
                    update={"metadata": {**issue.metadata, "review_history": history}}
                )
                self.save(issues)
                return
