"""Tests for QC issue taxonomy (P22-T1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_deep_research.content_gen.models import (
    QCIssue,
    QCIssueCategory,
    QCIssueSeverity,
    QCIssueStatus,
)
from cc_deep_research.content_gen.storage.qc_issue_store import QCIssueStore


class TestQCIssueModel:
    def test_issue_defaults_to_open(self) -> None:
        issue = QCIssue(
            category=QCIssueCategory.FACTUAL_RISK,
            description="Claim X is unsourced",
        )
        assert issue.status == QCIssueStatus.OPEN
        assert issue.severity == QCIssueSeverity.MEDIUM
        assert issue.is_open is True
        assert issue.is_resolved is False

    def test_critical_unresolved_blocks(self) -> None:
        issue = QCIssue(
            category=QCIssueCategory.COMPLIANCE_RISK,
            severity=QCIssueSeverity.CRITICAL,
            status=QCIssueStatus.OPEN,
            description="Potential legal issue",
        )
        assert issue.is_blocking is True

    def test_resolved_issue_is_not_blocking(self) -> None:
        issue = QCIssue(
            category=QCIssueCategory.COMPLIANCE_RISK,
            severity=QCIssueSeverity.CRITICAL,
            status=QCIssueStatus.RESOLVED,
            description="Issue was addressed",
        )
        assert issue.is_blocking is False

    def test_low_severity_not_blocking(self) -> None:
        issue = QCIssue(
            category=QCIssueCategory.PACING_PROBLEM,
            severity=QCIssueSeverity.LOW,
            status=QCIssueStatus.OPEN,
            description="Minor pacing note",
        )
        assert issue.is_blocking is False


class TestQCIssueStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> QCIssueStore:
        return QCIssueStore(path=tmp_path / "qc_issues.yaml")

    def test_add_issue(self, store: QCIssueStore) -> None:
        issue = QCIssue(
            category=QCIssueCategory.WEAK_HOOK,
            severity=QCIssueSeverity.HIGH,
            description="Hook lacks specificity",
            idea_id="idea-001",
        )
        stored = store.add(issue)
        assert len(stored) == 1
        assert stored[0].created_at != ""
        assert stored[0].updated_at != ""

    def test_get_issue(self, store: QCIssueStore) -> None:
        issue = QCIssue(
            category=QCIssueCategory.MISSING_EVIDENCE,
            description="No source for claim",
        )
        stored = store.add(issue)
        fetched = store.get(stored[0].issue_id)
        assert fetched is not None
        assert fetched.category == QCIssueCategory.MISSING_EVIDENCE

    def test_filter_by_category(self, store: QCIssueStore) -> None:
        issue1 = QCIssue(category=QCIssueCategory.FACTUAL_RISK, description="risk")
        issue2 = QCIssue(category=QCIssueCategory.WEAK_HOOK, description="hook")
        store.add(issue1)
        store.add(issue2)

        results = store.filter(category=QCIssueCategory.WEAK_HOOK)
        assert len(results) == 1
        assert results[0].category == QCIssueCategory.WEAK_HOOK

    def test_filter_by_severity(self, store: QCIssueStore) -> None:
        issue1 = QCIssue(category=QCIssueCategory.FACTUAL_RISK, severity=QCIssueSeverity.HIGH, description="h")
        issue2 = QCIssue(category=QCIssueCategory.FACTUAL_RISK, severity=QCIssueSeverity.LOW, description="l")
        store.add(issue1)
        store.add(issue2)

        results = store.filter(severity=QCIssueSeverity.HIGH)
        assert len(results) == 1
        assert results[0].severity == QCIssueSeverity.HIGH

    def test_filter_by_status(self, store: QCIssueStore) -> None:
        issue1 = QCIssue(category=QCIssueCategory.FACTUAL_RISK, description="open", status=QCIssueStatus.OPEN)
        issue2 = QCIssue(category=QCIssueCategory.FACTUAL_RISK, description="resolved", status=QCIssueStatus.RESOLVED)
        store.add(issue1)
        store.add(issue2)

        results = store.filter(status=QCIssueStatus.RESOLVED)
        assert len(results) == 1
        assert results[0].status == QCIssueStatus.RESOLVED

    def test_filter_by_idea_id(self, store: QCIssueStore) -> None:
        issue1 = QCIssue(category=QCIssueCategory.FACTUAL_RISK, description="i1", idea_id="idea-001")
        issue2 = QCIssue(category=QCIssueCategory.FACTUAL_RISK, description="i2", idea_id="idea-002")
        store.add(issue1)
        store.add(issue2)

        results = store.filter(idea_id="idea-001")
        assert len(results) == 1
        assert results[0].idea_id == "idea-001"

    def test_resolve_issue(self, store: QCIssueStore) -> None:
        issue = QCIssue(category=QCIssueCategory.OFF_BRAND_TONE, description="Tone mismatch")
        stored = store.add(issue)
        issue_id = stored[0].issue_id

        resolved = store.resolve(issue_id, "Adjusted tone to match brand", "operator")
        assert resolved is not None
        assert resolved.status == QCIssueStatus.RESOLVED
        assert resolved.resolution_note == "Adjusted tone to match brand"
        assert resolved.resolved_at != ""

    def test_dismiss_issue(self, store: QCIssueStore) -> None:
        issue = QCIssue(category=QCIssueCategory.CLARITY_ISSUE, description="Might be fine")
        stored = store.add(issue)
        issue_id = stored[0].issue_id

        dismissed = store.dismiss(issue_id, "Not actually an issue", "operator")
        assert dismissed is not None
        assert dismissed.status == QCIssueStatus.DISMISSED

    def test_get_blocking_issues(self, store: QCIssueStore) -> None:
        issue1 = QCIssue(
            category=QCIssueCategory.FACTUAL_RISK,
            severity=QCIssueSeverity.CRITICAL,
            status=QCIssueStatus.OPEN,
            idea_id="idea-001",
            description="Critical",
        )
        issue2 = QCIssue(
            category=QCIssueCategory.FACTUAL_RISK,
            severity=QCIssueSeverity.LOW,
            status=QCIssueStatus.OPEN,
            idea_id="idea-001",
            description="Low",
        )
        store.add(issue1)
        store.add(issue2)

        blocking = store.get_blocking_issues("idea-001")
        assert len(blocking) == 1
        assert blocking[0].severity == QCIssueSeverity.CRITICAL

    def test_update_issue(self, store: QCIssueStore) -> None:
        issue = QCIssue(category=QCIssueCategory.FACTUAL_RISK, description="Initial")
        stored = store.add(issue)
        issue_id = stored[0].issue_id

        updated = store.update(issue_id, {"status": QCIssueStatus.IN_REVIEW, "owner": "reviewer"})
        assert updated is not None
        assert updated.status == QCIssueStatus.IN_REVIEW
        assert updated.owner == "reviewer"
