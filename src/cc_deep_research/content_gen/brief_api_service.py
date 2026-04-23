"""Route-facing API service for brief HTTP workflows.

This service handles HTTP-level composition (request parsing, response shaping,
error classification) while delegating domain behavior to BriefService.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config, load_config
from cc_deep_research.content_gen.brief_service import (
    BriefService,
    ConcurrentModificationError,
)
from cc_deep_research.content_gen.models import (
    BriefLifecycleState,
    BriefProvenance,
    BriefRevision,
    ManagedOpportunityBrief,
    OpportunityBrief,
)
from cc_deep_research.content_gen.storage import AuditActor, AuditEventType, AuditStore

if TYPE_CHECKING:
    from cc_deep_research.content_gen.backlog_service import BacklogService


logger = logging.getLogger(__name__)


class BriefApiError(Exception):
    """Base class for brief API errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BriefNotFoundError(BriefApiError):
    """Raised when a brief does not exist."""

    def __init__(self, brief_id: str) -> None:
        super().__init__(f"Brief not found: {brief_id}", status_code=404)


class BriefValidationError(BriefApiError):
    """Raised when request validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class BriefConcurrentModificationError(BriefApiError):
    """Raised when a brief was modified by another actor since it was loaded."""

    def __init__(self, brief_id: str, expected: str, actual: str) -> None:
        self.brief_id = brief_id
        self.expected_updated_at = expected
        self.actual_updated_at = actual
        super().__init__(
            f"Brief '{brief_id}' was modified by another actor since it was last read. "
            f"Expected updated_at='{expected}', got '{actual}'. "
            f"Re-load the brief and retry the operation.",
            status_code=409,
        )


@dataclass
class ListBriefsResult:
    """Result of listing briefs."""

    items: list[ManagedOpportunityBrief]
    count: int


class BriefApiService:
    """API-level service for brief HTTP request handling.

    This class handles HTTP-specific concerns:
    - Request validation and parsing
    - Response shaping (serialization)
    - Error classification and mapping
    - HTTP workflow composition

    Domain behavior is delegated to BriefService.
    """

    def __init__(
        self,
        config: Config | None = None,
        brief_service: BriefService | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self._config = config or load_config()
        self._brief_service = brief_service or BriefService(self._config)
        if audit_store is not None:
            self._brief_service.set_audit_store(audit_store)
        elif self._brief_service._audit_store is None:
            self._brief_service.set_audit_store(AuditStore(config=self._config))
        self._audit_store = self._brief_service._audit_store

    @property
    def path(self) -> Path:
        """Return the brief store path."""
        return self._brief_service.path

    # ------------------------------------------------------------------
    # List / Get
    # ------------------------------------------------------------------

    def list_briefs(
        self,
        lifecycle_state: str | None = None,
        limit: int = 50,
    ) -> ListBriefsResult:
        """List all managed briefs with optional lifecycle state filtering.

        Args:
            lifecycle_state: Optional state filter (draft, approved, superseded, archived).
            limit: Maximum number of briefs to return.

        Returns:
            ListBriefsResult with items and count.

        Raises:
            BriefValidationError: If lifecycle_state is invalid.
        """
        output = self._brief_service.load()
        briefs = output.briefs

        if lifecycle_state:
            try:
                state = BriefLifecycleState(lifecycle_state)
                briefs = [b for b in briefs if b.lifecycle_state == state]
            except ValueError as exc:
                raise BriefValidationError(f"Invalid lifecycle_state: {lifecycle_state}") from exc

        # Sort by updated_at desc, take limit
        briefs = sorted(briefs, key=lambda b: b.updated_at, reverse=True)[:limit]
        return ListBriefsResult(items=briefs, count=len(briefs))

    def get_brief(self, brief_id: str) -> ManagedOpportunityBrief:
        """Get a single brief with its current head revision content.

        Args:
            brief_id: ID of the brief to retrieve.

        Returns:
            ManagedOpportunityBrief with current_revision attached.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
        """
        managed = self._brief_service.get_brief(brief_id)
        if managed is None:
            raise BriefNotFoundError(brief_id)
        return managed

    def get_brief_with_revision(
        self, brief_id: str
    ) -> tuple[ManagedOpportunityBrief, BriefRevision | None]:
        """Get a brief and its current head revision.

        Args:
            brief_id: ID of the brief to retrieve.

        Returns:
            Tuple of (ManagedOpportunityBrief, current_revision or None).

        Raises:
            BriefNotFoundError: If brief doesn't exist.
        """
        managed = self._brief_service.get_brief(brief_id)
        if managed is None:
            raise BriefNotFoundError(brief_id)
        revision = self._brief_service.get_revision(managed.current_revision_id)
        return managed, revision

    # ------------------------------------------------------------------
    # Create / Update
    # ------------------------------------------------------------------

    def create_brief(
        self,
        brief_data: dict[str, Any],
        provenance: str = "generated",
        source_pipeline_id: str = "",
        revision_notes: str = "",
    ) -> ManagedOpportunityBrief:
        """Create a new managed brief from an OpportunityBrief payload.

        Args:
            brief_data: OpportunityBrief fields as a dictionary.
            provenance: Provenance string (generated, imported, cloned, branched, operator_created).
            source_pipeline_id: Pipeline ID that generated this brief.
            revision_notes: Notes for the initial revision.

        Returns:
            Created ManagedOpportunityBrief.

        Raises:
            BriefValidationError: If brief_data is invalid.
        """
        try:
            opportunity = OpportunityBrief.model_validate(brief_data)
        except Exception as exc:
            raise BriefValidationError(f"Invalid brief data: {exc}") from exc

        provenance_enum = BriefProvenance(provenance) if provenance else BriefProvenance.GENERATED

        managed = self._brief_service.create_from_opportunity(
            opportunity,
            provenance=provenance_enum,
            source_pipeline_id=source_pipeline_id,
            revision_notes=revision_notes,
        )
        return managed

    def update_brief(
        self,
        brief_id: str,
        patch: dict[str, Any],
        expected_updated_at: str | None = None,
    ) -> ManagedOpportunityBrief:
        """Update brief metadata (title, etc.).

        Args:
            brief_id: ID of the brief to update.
            patch: Fields to update.
            expected_updated_at: Expected updated_at for optimistic concurrency.

        Returns:
            Updated ManagedOpportunityBrief.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
            BriefConcurrentModificationError: If expected_updated_at doesn't match.
            BriefValidationError: If patch contains immutable fields.
        """
        try:
            updated = self._brief_service.update_brief(
                brief_id,
                patch,
                expected_updated_at=expected_updated_at,
            )
        except ConcurrentModificationError as exc:
            raise BriefConcurrentModificationError(
                exc.brief_id, exc.expected_updated_at, exc.actual_updated_at
            ) from exc

        if updated is None:
            raise BriefNotFoundError(brief_id)
        return updated

    # ------------------------------------------------------------------
    # Revision management
    # ------------------------------------------------------------------

    def save_revision(
        self,
        brief_id: str,
        brief_data: dict[str, Any],
        revision_notes: str = "",
        source_pipeline_id: str = "",
        expected_updated_at: str | None = None,
    ) -> BriefRevision:
        """Save a new revision of an existing brief.

        The current_revision_id (head) is NOT changed by this operation.
        Use update_head() to promote a revision to head.

        Args:
            brief_id: ID of the brief to revise.
            brief_data: OpportunityBrief fields as a dictionary.
            revision_notes: Notes for this revision.
            source_pipeline_id: Pipeline ID that generated this revision.
            expected_updated_at: Expected updated_at for optimistic concurrency.

        Returns:
            Created BriefRevision.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
            BriefConcurrentModificationError: If expected_updated_at doesn't match.
            BriefValidationError: If brief_data is invalid.
        """
        try:
            opportunity = OpportunityBrief.model_validate(brief_data)
        except Exception as exc:
            raise BriefValidationError(f"Invalid brief data: {exc}") from exc

        try:
            revision = self._brief_service.save_revision(
                brief_id,
                opportunity,
                revision_notes=revision_notes,
                source_pipeline_id=source_pipeline_id,
                expected_updated_at=expected_updated_at,
            )
        except ConcurrentModificationError as exc:
            raise BriefConcurrentModificationError(
                exc.brief_id, exc.expected_updated_at, exc.actual_updated_at
            ) from exc

        if revision is None:
            raise BriefNotFoundError(brief_id)
        return revision

    def update_head(
        self,
        brief_id: str,
        revision_id: str,
        expected_updated_at: str | None = None,
    ) -> ManagedOpportunityBrief:
        """Update the current_revision_id (head) to an existing revision.

        Args:
            brief_id: ID of the brief to update.
            revision_id: The revision_id to set as current head.
            expected_updated_at: Expected updated_at for optimistic concurrency.

        Returns:
            Updated ManagedOpportunityBrief.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
            BriefConcurrentModificationError: If expected_updated_at doesn't match.
        """
        try:
            updated = self._brief_service.update_head(
                brief_id,
                revision_id,
                expected_updated_at=expected_updated_at,
            )
        except ConcurrentModificationError as exc:
            raise BriefConcurrentModificationError(
                exc.brief_id, exc.expected_updated_at, exc.actual_updated_at
            ) from exc

        if updated is None:
            raise BriefNotFoundError(brief_id)
        return updated

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def approve_brief(
        self, brief_id: str, expected_updated_at: str | None = None
    ) -> ManagedOpportunityBrief:
        """Transition a brief to the approved state.

        Args:
            brief_id: ID of the brief to approve.
            expected_updated_at: Expected updated_at for optimistic concurrency.

        Returns:
            Updated ManagedOpportunityBrief.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
            BriefConcurrentModificationError: If expected_updated_at doesn't match.
        """
        return self._transition_lifecycle(brief_id, BriefLifecycleState.APPROVED, expected_updated_at)

    def archive_brief(
        self, brief_id: str, expected_updated_at: str | None = None
    ) -> ManagedOpportunityBrief:
        """Archive a brief.

        Args:
            brief_id: ID of the brief to archive.
            expected_updated_at: Expected updated_at for optimistic concurrency.

        Returns:
            Updated ManagedOpportunityBrief.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
            BriefConcurrentModificationError: If expected_updated_at doesn't match.
        """
        return self._transition_lifecycle(brief_id, BriefLifecycleState.ARCHIVED, expected_updated_at)

    def supersede_brief(
        self, brief_id: str, expected_updated_at: str | None = None
    ) -> ManagedOpportunityBrief:
        """Mark a brief as superseded.

        Args:
            brief_id: ID of the brief to supersede.
            expected_updated_at: Expected updated_at for optimistic concurrency.

        Returns:
            Updated ManagedOpportunityBrief.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
            BriefConcurrentModificationError: If expected_updated_at doesn't match.
        """
        return self._transition_lifecycle(brief_id, BriefLifecycleState.SUPERSEDED, expected_updated_at)

    def revert_to_draft(
        self, brief_id: str, expected_updated_at: str | None = None
    ) -> ManagedOpportunityBrief:
        """Revert a brief back to draft state.

        Args:
            brief_id: ID of the brief to revert.
            expected_updated_at: Expected updated_at for optimistic concurrency.

        Returns:
            Updated ManagedOpportunityBrief.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
            BriefConcurrentModificationError: If expected_updated_at doesn't match.
        """
        return self._transition_lifecycle(brief_id, BriefLifecycleState.DRAFT, expected_updated_at)

    def _transition_lifecycle(
        self,
        brief_id: str,
        target_state: BriefLifecycleState,
        expected_updated_at: str | None = None,
    ) -> ManagedOpportunityBrief:
        """Apply a lifecycle state transition.

        Args:
            brief_id: ID of the brief to transition.
            target_state: The target lifecycle state.
            expected_updated_at: Expected updated_at for optimistic concurrency.

        Returns:
            Updated ManagedOpportunityBrief.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
            BriefConcurrentModificationError: If expected_updated_at doesn't match.
        """
        try:
            updated = self._brief_service._transition_lifecycle(
                brief_id, target_state, expected_updated_at
            )
        except ConcurrentModificationError as exc:
            raise BriefConcurrentModificationError(
                exc.brief_id, exc.expected_updated_at, exc.actual_updated_at
            ) from exc

        if updated is None:
            raise BriefNotFoundError(brief_id)
        return updated

    # ------------------------------------------------------------------
    # Clone / Branch
    # ------------------------------------------------------------------

    def clone_brief(
        self,
        brief_id: str,
        new_title: str | None = None,
    ) -> ManagedOpportunityBrief:
        """Clone an existing brief.

        The clone starts with the same current head revision but is otherwise
        independent. Returns the new brief in DRAFT state.

        Args:
            brief_id: ID of the brief to clone.
            new_title: Optional new title for the clone.

        Returns:
            New ManagedOpportunityBrief in DRAFT state.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
        """
        cloned = self._brief_service.clone_brief(brief_id, new_title=new_title)
        if cloned is None:
            raise BriefNotFoundError(brief_id)
        return cloned

    def branch_brief(
        self,
        brief_id: str,
        new_title: str | None = None,
        branch_reason: str = "",
    ) -> ManagedOpportunityBrief:
        """Create a branched copy of an existing brief.

        Branch creates a derivative brief that tracks its lineage back to the source.
        The branched brief starts in DRAFT state with a copy of the current head revision.

        Args:
            brief_id: ID of the brief to branch.
            new_title: Optional new title for the branch.
            branch_reason: Reason for branching.

        Returns:
            New ManagedOpportunityBrief in DRAFT state.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
        """
        branched = self._brief_service.branch_brief(
            brief_id,
            new_title=new_title,
            branch_reason=branch_reason,
        )
        if branched is None:
            raise BriefNotFoundError(brief_id)
        return branched

    # ------------------------------------------------------------------
    # Siblings / Compare
    # ------------------------------------------------------------------

    def list_sibling_briefs(self, brief_id: str) -> list[ManagedOpportunityBrief]:
        """List briefs that share the same source brief.

        Args:
            brief_id: ID of the brief whose siblings to find.

        Returns:
            List of sibling briefs.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
        """
        managed = self._brief_service.get_brief(brief_id)
        if managed is None:
            raise BriefNotFoundError(brief_id)

        siblings = self._brief_service.list_sibling_briefs(brief_id)

        # Include the source brief itself if this is a branch
        result_briefs = [managed]
        if managed.source_brief_id:
            source = self._brief_service.get_brief(managed.source_brief_id)
            if source:
                result_briefs = [source] + siblings

        return result_briefs

    def compare_briefs(
        self, brief_id: str, other_brief_id: str
    ) -> tuple[ManagedOpportunityBrief, BriefRevision | None, ManagedOpportunityBrief, BriefRevision | None]:
        """Compare two briefs side by side.

        Args:
            brief_id: ID of the first brief.
            other_brief_id: ID of the second brief.

        Returns:
            Tuple of (brief_a, revision_a, brief_b, revision_b).

        Raises:
            BriefNotFoundError: If either brief doesn't exist.
        """
        brief_a = self._brief_service.get_brief(brief_id)
        brief_b = self._brief_service.get_brief(other_brief_id)

        if brief_a is None or brief_b is None:
            raise BriefNotFoundError(brief_id if brief_a is None else other_brief_id)

        revision_a = self._brief_service.get_revision(brief_a.current_revision_id)
        revision_b = self._brief_service.get_revision(brief_b.current_revision_id)

        return brief_a, revision_a, brief_b, revision_b

    # ------------------------------------------------------------------
    # Revision access
    # ------------------------------------------------------------------

    def get_revision(self, revision_id: str) -> BriefRevision | None:
        """Get a specific revision by ID.

        Args:
            revision_id: ID of the revision to retrieve.

        Returns:
            BriefRevision or None if not found.
        """
        return self._brief_service.get_revision(revision_id)

    def list_revisions(self, brief_id: str, limit: int = 50) -> list[BriefRevision]:
        """List all revisions for a brief, most recent first.

        Args:
            brief_id: ID of the brief whose revisions to list.
            limit: Maximum number of revisions to return.

        Returns:
            List of BriefRevision objects.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
        """
        # First check brief exists
        managed = self._brief_service.get_brief(brief_id)
        if managed is None:
            raise BriefNotFoundError(brief_id)
        return self._brief_service.list_revisions(brief_id, limit=limit)

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def get_audit_history(
        self,
        brief_id: str,
        event_type: str | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit history for a specific brief.

        Args:
            brief_id: ID of the brief whose audit history to retrieve.
            event_type: Optional event type filter.
            actor: Optional actor filter.
            limit: Maximum number of entries to return.

        Returns:
            List of audit entry dictionaries.

        Raises:
            BriefNotFoundError: If brief doesn't exist.
        """
        # Check brief exists
        managed = self._brief_service.get_brief(brief_id)
        if managed is None:
            raise BriefNotFoundError(brief_id)

        event_type_enum = AuditEventType(event_type) if event_type else None
        actor_enum = AuditActor(actor) if actor else None
        entries = self._audit_store.load_entries(
            brief_id=brief_id,
            event_type=event_type_enum,
            actor=actor_enum,
            limit=limit,
        )
        return [entry.to_dict() for entry in entries]

    # ------------------------------------------------------------------
    # Backlog generation (brief-to-backlog)
    # ------------------------------------------------------------------

    def apply_backlog_items(
        self,
        brief_id: str,
        items: list[dict[str, Any]],
        backlog_service: BacklogService,
    ) -> tuple[int, list[Any], list[str]]:
        """Apply generated backlog items from a brief to the persistent backlog.

        Args:
            brief_id: ID of the source brief.
            items: List of item data dictionaries to create.
            backlog_service: BacklogService instance for persistence.

        Returns:
            Tuple of (applied_count, created_items, errors).

        Raises:
            BriefNotFoundError: If brief doesn't exist.
        """
        managed = self._brief_service.get_brief(brief_id)
        if managed is None:
            raise BriefNotFoundError(brief_id)

        revision = self._brief_service.get_revision(managed.current_revision_id)
        if revision is None:
            raise BriefValidationError("No current revision found")

        applied_count = 0
        created_items: list[Any] = []
        errors: list[str] = []

        for index, item_data in enumerate(items, start=1):
            try:
                if not item_data.get("title") and not item_data.get("idea"):
                    errors.append(f"Item {index}: missing title or idea")
                    continue

                created = backlog_service.create_item(
                    title=str(item_data.get("title", "")),
                    one_line_summary=str(item_data.get("one_line_summary", "")),
                    raw_idea=str(item_data.get("raw_idea", "")),
                    constraints=str(item_data.get("constraints", "")),
                    idea=str(item_data.get("idea", item_data.get("title", ""))),
                    category=str(item_data.get("category", "authority-building")),
                    audience=str(item_data.get("audience", "")),
                    persona_detail=str(item_data.get("persona_detail", "")),
                    problem=str(item_data.get("problem", "")),
                    emotional_driver=str(item_data.get("emotional_driver", "")),
                    urgency_level=str(item_data.get("urgency_level", "medium")),
                    source=str(item_data.get("source", "")),
                    why_now=str(item_data.get("why_now", "")),
                    hook=str(item_data.get("hook", "")),
                    content_type=str(item_data.get("content_type", "")),
                    key_message=str(item_data.get("key_message", "")),
                    call_to_action=str(item_data.get("call_to_action", "")),
                    evidence=str(item_data.get("evidence", "")),
                    risk_level=str(item_data.get("risk_level", "medium")),
                    source_theme=str(item_data.get("source_theme", managed.title or brief_id)),
                    selection_reasoning=str(item_data.get("reason", "")),
                )
                applied_count += 1
                created_items.append(created)

                # Log brief origin on the backlog item
                self._audit_store.log_backlog_mutation(
                    event_type=AuditEventType.ITEM_CREATED,
                    idea_id=created.idea_id,
                    actor=AuditActor.OPERATOR,
                    patch={
                        "source_brief_id": brief_id,
                        "source_revision_id": revision.revision_id,
                        "source_revision_version": revision.version,
                        "brief_theme": managed.title,
                    },
                    outcome="success",
                )
            except Exception as exc:
                errors.append(f"Item {index}: {exc}")

        return applied_count, created_items, errors

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_brief(brief: ManagedOpportunityBrief) -> dict[str, Any]:
        """Serialize a ManagedOpportunityBrief to JSON-compatible dict."""
        return json.loads(brief.model_dump_json())

    @staticmethod
    def serialize_revision(revision: BriefRevision) -> dict[str, Any]:
        """Serialize a BriefRevision to JSON-compatible dict."""
        return json.loads(revision.model_dump_json())

    @staticmethod
    def serialize_brief_with_revision(
        brief: ManagedOpportunityBrief, revision: BriefRevision | None
    ) -> dict[str, Any]:
        """Serialize a brief with its current head revision."""
        result = json.loads(brief.model_dump_json())
        if revision:
            result["current_revision"] = json.loads(revision.model_dump_json())
        return result

    def serialize_list(self, result: ListBriefsResult) -> dict[str, Any]:
        """Serialize the brief list response.

        Args:
            result: ListBriefsResult from list_briefs().

        Returns:
            Dict with items and count.
        """
        return {
            "items": [self.serialize_brief(b) for b in result.items],
            "count": result.count,
        }
