"""Managed brief persistence and lifecycle helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.models import (
    BriefLifecycleState,
    BriefProvenance,
    BriefRevision,
    ManagedBriefOutput,
    ManagedOpportunityBrief,
    OpportunityBrief,
)
from cc_deep_research.content_gen.storage import (
    AuditActor,
    AuditEventType,
    AuditStore,
    BriefStore,
    SqliteBriefStore,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config


_BRIEF_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _validate_brief_id(brief_id: str) -> str:
    """Validate brief_id format to prevent injection and malformed identifiers."""
    if not brief_id or not isinstance(brief_id, str):
        raise ValueError("brief_id must be a non-empty string")
    if not _BRIEF_ID_RE.match(brief_id):
        raise ValueError(
            f"brief_id '{brief_id}' contains invalid characters; use only alphanumeric, hyphen, underscore"
        )
    return brief_id


class BriefService:
    """Coordinate brief persistence, lifecycle transitions, and revision management.

    This service owns all write operations on managed briefs. Routes and UI code
    must not write raw brief payloads directly.
    """

    def __init__(
        self,
        config: Config | None = None,
        store: BriefStore | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        if store is not None:
            self._store = store
        else:
            use_sqlite = getattr(getattr(config, "content_gen", None), "use_sqlite", False)
            path: Path | None = None
            configured_path = getattr(getattr(config, "content_gen", None), "brief_path", None)
            if configured_path:
                path = Path(configured_path).expanduser()

            if use_sqlite:
                self._store = SqliteBriefStore(config=config)
            else:
                self._store = BriefStore(path)

        self._audit_store = audit_store

    def set_audit_store(self, audit_store: AuditStore) -> None:
        """Attach an audit store for governance tracking."""
        self._audit_store = audit_store

    @property
    def path(self) -> Path:
        return self._store.path

    def load(self) -> ManagedBriefOutput:
        """Load all managed briefs."""
        return self._store.load()

    def get_brief(self, brief_id: str) -> ManagedOpportunityBrief | None:
        """Load a single managed brief by ID."""
        _validate_brief_id(brief_id)
        output = self._store.load()
        return next((b for b in output.briefs if b.brief_id == brief_id), None)

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------

    def create_from_opportunity(
        self,
        opportunity: OpportunityBrief,
        *,
        provenance: BriefProvenance = BriefProvenance.GENERATED,
        source_pipeline_id: str = "",
        revision_notes: str = "",
    ) -> ManagedOpportunityBrief:
        """Create a new managed brief from an OpportunityBrief (typically pipeline stage 1 output).

        This creates a new brief resource with a single initial revision.
        """
        now = _now_iso()
        brief_id = f"mbrief_{opportunity.brief_id}" if opportunity.brief_id else f"mbrief_{now[:10]}"

        # Build the first revision
        revision = BriefRevision(
            brief_id=brief_id,
            version=1,
            theme=opportunity.theme,
            goal=opportunity.goal,
            primary_audience_segment=opportunity.primary_audience_segment,
            secondary_audience_segments=opportunity.secondary_audience_segments,
            problem_statements=opportunity.problem_statements,
            content_objective=opportunity.content_objective,
            proof_requirements=opportunity.proof_requirements,
            platform_constraints=opportunity.platform_constraints,
            risk_constraints=opportunity.risk_constraints,
            freshness_rationale=opportunity.freshness_rationale,
            sub_angles=opportunity.sub_angles,
            research_hypotheses=opportunity.research_hypotheses,
            success_criteria=opportunity.success_criteria,
            expert_take=opportunity.expert_take,
            non_obvious_claims_to_test=opportunity.non_obvious_claims_to_test,
            genericity_risks=opportunity.genericity_risks,
            provenance=provenance,
            is_generated=opportunity.is_generated,
            revision_notes=revision_notes or "Initial brief creation",
            source_pipeline_id=source_pipeline_id,
            created_at=now,
        )

        # Build the managed brief resource
        managed = ManagedOpportunityBrief(
            brief_id=brief_id,
            title=opportunity.theme or "Untitled brief",
            lifecycle_state=BriefLifecycleState.DRAFT,
            current_revision_id=revision.revision_id,
            latest_revision_id=revision.revision_id,
            revision_count=1,
            provenance=provenance,
            created_at=now,
            updated_at=now,
            revision_history=[f"v1: {revision.revision_notes}"],
        )

        # Persist
        output = self._store.load()
        output.briefs.append(managed)
        self._store.save(output)

        self._audit_mutation(
            AuditEventType.ITEM_CREATED,
            brief_id,
            actor=AuditActor.SYSTEM,
            patch={"provenance": provenance.value, "source_pipeline_id": source_pipeline_id},
            brief_snapshot=managed,
            outcome="success",
        )

        return managed

    # -------------------------------------------------------------------------
    # Revision management
    # -------------------------------------------------------------------------

    def save_revision(
        self,
        brief_id: str,
        opportunity: OpportunityBrief,
        *,
        revision_notes: str = "",
        source_pipeline_id: str = "",
    ) -> BriefRevision | None:
        """Save a new revision of an existing managed brief.

        Creates an immutable revision snapshot and advances the latest_revision_id.
        Does NOT change the current_revision_id (head) - use update_head for that.
        """
        _validate_brief_id(brief_id)
        output = self._store.load()
        managed = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if managed is None:
            return None

        now = _now_iso()
        new_version = managed.revision_count + 1

        revision = BriefRevision(
            brief_id=brief_id,
            version=new_version,
            theme=opportunity.theme,
            goal=opportunity.goal,
            primary_audience_segment=opportunity.primary_audience_segment,
            secondary_audience_segments=opportunity.secondary_audience_segments,
            problem_statements=opportunity.problem_statements,
            content_objective=opportunity.content_objective,
            proof_requirements=opportunity.proof_requirements,
            platform_constraints=opportunity.platform_constraints,
            risk_constraints=opportunity.risk_constraints,
            freshness_rationale=opportunity.freshness_rationale,
            sub_angles=opportunity.sub_angles,
            research_hypotheses=opportunity.research_hypotheses,
            success_criteria=opportunity.success_criteria,
            expert_take=opportunity.expert_take,
            non_obvious_claims_to_test=opportunity.non_obvious_claims_to_test,
            genericity_risks=opportunity.genericity_risks,
            provenance=BriefProvenance.OPERATOR_CREATED
            if not opportunity.is_generated
            else BriefProvenance.GENERATED,
            is_generated=opportunity.is_generated,
            revision_notes=revision_notes or f"Revision v{new_version}",
            source_pipeline_id=source_pipeline_id,
            created_at=now,
        )

        # Update managed brief metadata (not the head)
        managed.revision_count = new_version
        managed.latest_revision_id = revision.revision_id
        managed.updated_at = now
        managed.revision_history = managed.revision_history + [f"v{new_version}: {revision.revision_notes}"]

        self._store.save(output)
        return revision

    def update_head(
        self,
        brief_id: str,
        revision_id: str,
        actor: AuditActor = AuditActor.OPERATOR,
    ) -> ManagedOpportunityBrief | None:
        """Update the current_revision_id (head) to an existing revision.

        This is how approved revisions become active.
        """
        _validate_brief_id(brief_id)
        output = self._store.load()
        managed = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if managed is None:
            return None

        if not any(r.revision_id == revision_id for r in [self._get_revision(managed, output, revision_id)]):
            # Revision doesn't belong to this brief or doesn't exist
            existing_rev_ids = [r.revision_id for r in [self._get_revision(managed, output, rid) for rid in [managed.current_revision_id, managed.latest_revision_id]] if r is not None]
            if revision_id not in existing_rev_ids:
                return None

        now = _now_iso()
        managed.current_revision_id = revision_id
        managed.updated_at = now

        self._store.save(output)
        self._audit_mutation(
            AuditEventType.ITEM_STATUS_CHANGED,
            brief_id,
            actor=actor,
            patch={"current_revision_id": revision_id},
            brief_snapshot=managed,
            outcome="success",
        )
        return managed

    def _get_revision(
        self, brief: ManagedOpportunityBrief, output: ManagedBriefOutput, revision_id: str
    ) -> BriefRevision | None:
        """Get a revision by ID from the output (placeholder - revisions are stored separately)."""
        # In a full implementation, revisions would be stored in their own store/table
        # For now, return None - the revision store is out of scope for P1
        return None

    # -------------------------------------------------------------------------
    # Lifecycle transitions
    # -------------------------------------------------------------------------

    def approve(self, brief_id: str) -> ManagedOpportunityBrief | None:
        """Transition a brief to the approved state."""
        return self._transition_lifecycle(brief_id, BriefLifecycleState.APPROVED)

    def archive(self, brief_id: str) -> ManagedOpportunityBrief | None:
        """Archive a brief."""
        return self._transition_lifecycle(brief_id, BriefLifecycleState.ARCHIVED)

    def supersede(self, brief_id: str) -> ManagedOpportunityBrief | None:
        """Mark a brief as superseded by a newer version."""
        return self._transition_lifecycle(brief_id, BriefLifecycleState.SUPERSEDED)

    def revert_to_draft(self, brief_id: str) -> ManagedOpportunityBrief | None:
        """Revert a brief back to draft state."""
        return self._transition_lifecycle(brief_id, BriefLifecycleState.DRAFT)

    def _transition_lifecycle(
        self,
        brief_id: str,
        target_state: BriefLifecycleState,
    ) -> ManagedOpportunityBrief | None:
        """Apply a lifecycle state transition."""
        _validate_brief_id(brief_id)
        now = _now_iso()
        updated = self._store.update_brief(
            brief_id,
            {"lifecycle_state": target_state.value, "updated_at": now},
        )
        if updated is not None:
            self._audit_mutation(
                AuditEventType.ITEM_STATUS_CHANGED,
                brief_id,
                actor=AuditActor.OPERATOR,
                patch={"lifecycle_state": target_state.value},
                brief_snapshot=updated,
                outcome="success",
            )
        return updated

    # -------------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------------

    def update_brief(
        self,
        brief_id: str,
        patch: dict[str, Any],
    ) -> ManagedOpportunityBrief | None:
        """Apply a partial brief update with timestamp management."""
        _validate_brief_id(brief_id)
        normalized = _normalize_brief_patch(patch)
        normalized["updated_at"] = _now_iso()
        updated = self._store.update_brief(brief_id, normalized)
        if updated is not None:
            self._audit_mutation(
                AuditEventType.ITEM_UPDATED,
                brief_id,
                actor=AuditActor.OPERATOR,
                patch=patch,
                brief_snapshot=updated,
                outcome="success",
            )
        return updated

    def delete_brief(self, brief_id: str) -> bool:
        """Archive a brief instead of hard delete to preserve audit trail."""
        _validate_brief_id(brief_id)
        return self.archive(brief_id) is not None

    # -------------------------------------------------------------------------
    # Audit
    # -------------------------------------------------------------------------

    def _audit_mutation(
        self,
        event_type: AuditEventType,
        brief_id: str,
        actor: AuditActor = AuditActor.OPERATOR,
        patch: dict[str, Any] | None = None,
        brief_snapshot: ManagedOpportunityBrief | None = None,
        outcome: str = "success",
    ) -> None:
        """Log a brief mutation to audit store if configured."""
        if self._audit_store is None:
            return
        self._audit_store.log_backlog_mutation(
            event_type=event_type,
            idea_id=brief_id,  # Reuse idea_id field for brief_id
            actor=actor,
            patch=patch,
            item_snapshot=None,  # AuditStore.log_backlog_mutation expects BacklogItem
            outcome=outcome,
        )


def _normalize_brief_patch(patch: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate patch keys for managed briefs."""
    normalized = dict(patch)

    # Only allow editing of mutable fields
    mutable_fields = {
        "title",
        "lifecycle_state",
        "revision_history",
    }
    unsupported = sorted(set(patch) - mutable_fields)
    if unsupported:
        raise ValueError(
            "The following fields cannot be patched directly: "
            + ", ".join(unsupported)
            + ". Use save_revision() to create new content revisions."
        )

    return normalized
