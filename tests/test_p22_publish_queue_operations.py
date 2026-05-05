"""Tests for publish queue operations (P22-T3)."""

from __future__ import annotations

import pytest

from cc_deep_research.content_gen.models import (
    PublishItem,
    PublishReadinessState,
    DraftLaneDecision,
)
from cc_deep_research.content_gen.models.publish_queue import (
    PublishBlocker,
    PublishQueueOperatorNote,
    PublishQueueReviewEntry,
)


class TestPublishItemReadinessState:
    def test_publish_item_defaults_to_draft(self) -> None:
        item = PublishItem(idea_id="idea-001", platform="youtube")
        assert item.readiness == PublishReadinessState.DRAFT

    def test_publish_item_readiness_transitions(self) -> None:
        item = PublishItem(idea_id="idea-001", platform="youtube", readiness=PublishReadinessState.NEEDS_REVIEW)
        assert item.readiness == PublishReadinessState.NEEDS_REVIEW

        item = item.model_copy(update={"readiness": PublishReadinessState.BLOCKED})
        assert item.readiness == PublishReadinessState.BLOCKED

        item = item.model_copy(update={"readiness": PublishReadinessState.READY})
        assert item.readiness == PublishReadinessState.READY

        item = item.model_copy(update={"readiness": PublishReadinessState.SCHEDULED})
        assert item.readiness == PublishReadinessState.SCHEDULED

        item = item.model_copy(update={"readiness": PublishReadinessState.PUBLISHED})
        assert item.readiness == PublishReadinessState.PUBLISHED

    def test_publish_item_blocker_ids_list(self) -> None:
        item = PublishItem(
            idea_id="idea-001",
            platform="youtube",
            blocker_ids=["blk_001", "blk_002"],
        )
        assert len(item.blocker_ids) == 2
        assert "blk_001" in item.blocker_ids

    def test_publish_item_review_history(self) -> None:
        item = PublishItem(
            idea_id="idea-001",
            platform="youtube",
            review_history=[
                {"action": "submitted_for_review", "actor": "operator", "created_at": "2026-05-01T00:00:00Z"},
                {"action": "approved", "actor": "admin", "created_at": "2026-05-01T01:00:00Z"},
            ],
        )
        assert len(item.review_history) == 2
        assert item.review_history[0]["action"] == "submitted_for_review"

    def test_publish_item_operator_notes(self) -> None:
        item = PublishItem(
            idea_id="idea-001",
            platform="youtube",
            operator_notes=["Check thumbnail font", "Verify claim sourcing"],
        )
        assert len(item.operator_notes) == 2


class TestPublishBlockerModel:
    def test_blocker_defaults_unresolved(self) -> None:
        blocker = PublishBlocker(
            blocker_type="qc_issue",
            idea_id="idea-001",
            platform="youtube",
            description="Critical claim not verified",
        )
        assert blocker.is_resolved is False
        assert blocker.resolved_at == ""

    def test_blocker_with_related_issues(self) -> None:
        blocker = PublishBlocker(
            blocker_type="qc_issue",
            idea_id="idea-001",
            platform="youtube",
            description="QC issue blocking publish",
            related_issue_ids=["qci_001", "qci_002"],
        )
        assert len(blocker.related_issue_ids) == 2

    def test_blocker_severity_levels(self) -> None:
        for severity in ("low", "medium", "high", "critical"):
            blocker = PublishBlocker(
                blocker_type="missing_asset",
                severity=severity,
                idea_id="idea-001",
                platform="youtube",
                description="Asset missing",
            )
            assert blocker.severity == severity


class TestPublishQueueReviewEntry:
    def test_review_entry_fields(self) -> None:
        entry = PublishQueueReviewEntry(
            idea_id="idea-001",
            platform="youtube",
            action="approved",
            actor="operator",
            note="All QC issues resolved",
            old_readiness=PublishReadinessState.NEEDS_REVIEW,
            new_readiness=PublishReadinessState.READY,
        )
        assert entry.action == "approved"
        assert entry.old_readiness == PublishReadinessState.NEEDS_REVIEW
        assert entry.new_readiness == PublishReadinessState.READY


class TestPublishQueueOperatorNote:
    def test_operator_note_fields(self) -> None:
        note = PublishQueueOperatorNote(
            idea_id="idea-001",
            platform="youtube",
            content="Consider delaying by 1 week for better data",
            author="strategist",
        )
        assert note.content == "Consider delaying by 1 week for better data"
        assert note.author == "strategist"


class TestReadinessStateEnum:
    def test_all_readiness_states(self) -> None:
        assert PublishReadinessState.DRAFT.value == "draft"
        assert PublishReadinessState.NEEDS_REVIEW.value == "needs_review"
        assert PublishReadinessState.BLOCKED.value == "blocked"
        assert PublishReadinessState.READY.value == "ready"
        assert PublishReadinessState.SCHEDULED.value == "scheduled"
        assert PublishReadinessState.PUBLISHED.value == "published"
        assert PublishReadinessState.ARCHIVED.value == "archived"

    def test_publish_item_with_all_new_fields(self) -> None:
        item = PublishItem(
            idea_id="idea-001",
            platform="youtube",
            publish_datetime="2026-05-10T12:00:00Z",
            status="scheduled",
            readiness=PublishReadinessState.SCHEDULED,
            blocker_ids=["blk_abc"],
            review_history=[
                {"action": "readiness_changed: draft -> needs_review", "actor": "operator", "created_at": "2026-05-01T00:00:00Z"},
            ],
            operator_notes=["Note about timing"],
        )
        assert item.readiness == PublishReadinessState.SCHEDULED
        assert item.blocker_ids == ["blk_abc"]
        assert len(item.review_history) == 1
        assert len(item.operator_notes) == 1