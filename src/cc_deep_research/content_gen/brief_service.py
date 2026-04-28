"""Managed brief persistence and lifecycle helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from cc_deep_research.content_gen.models.brief import (
    BriefRevision,
    ManagedBriefOutput,
    ManagedOpportunityBrief,
    OpportunityBrief,
)
from cc_deep_research.content_gen.models.pipeline import get_phase_policy
from cc_deep_research.content_gen.models.shared import (
    BriefLifecycleState,
    BriefProvenance,
    OperatingPhase,
)
from cc_deep_research.content_gen.storage import (
    AuditActor,
    AuditEventType,
    AuditStore,
    BriefRevisionStore,
    BriefStore,
    SqliteBriefStore,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config


class ConcurrentModificationError(ValueError):
    """Raised when a brief was modified by another actor since it was loaded.

    This enables optimistic concurrency: the caller should re-load the brief
    and retry the operation with the fresh updated_at value.
    """

    def __init__(self, brief_id: str, expected: str, actual: str) -> None:
        self.brief_id = brief_id
        self.expected_updated_at = expected
        self.actual_updated_at = actual
        super().__init__(
            f"Brief '{brief_id}' was modified by another actor since it was last read. "
            f"Expected updated_at='{expected}', got '{actual}'. "
            f"Re-load the brief and retry the operation."
        )


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


def _default_operating_policies() -> list[Any]:
    return [get_phase_policy(phase) for phase in OperatingPhase]


class BriefService:
    """Coordinate brief persistence, lifecycle transitions, and revision management.

    This service owns all write operations on managed briefs. Routes and UI code
    must not write raw brief payloads directly.
    """

    def __init__(
        self,
        config: Config | None = None,
        store: BriefStore | None = None,
        revision_store: BriefRevisionStore | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        if store is not None:
            self._store = store
        else:
            content_gen_cfg = getattr(config, "content_gen", None) or type("Empty", (), {})()
            use_sqlite = getattr(content_gen_cfg, "use_sqlite", False)
            path: Path | None = None
            configured_path = getattr(content_gen_cfg, "brief_path", None)
            if configured_path:
                path = Path(configured_path).expanduser()

            if use_sqlite:
                self._store = SqliteBriefStore(config=config)
            else:
                self._store = BriefStore(path)

        if revision_store is not None:
            self._revision_store = revision_store
        else:
            self._revision_store = BriefRevisionStore(config=config)

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
            operating_policies=_default_operating_policies(),
        )

        # Persist revision first
        self._revision_store.save_revision(revision)

        # Persist managed brief
        output = self._store.load()
        output.briefs.append(managed)
        self._store.save(output)

        self._audit_mutation(
            AuditEventType.BRIEF_CREATED,
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
        expected_updated_at: str | None = None,
    ) -> BriefRevision | None:
        """Save a new revision of an existing managed brief.

        Creates an immutable revision snapshot and advances the latest_revision_id.
        Does NOT change the current_revision_id (head) - use update_head for that.

        Raises ConcurrentModificationError if expected_updated_at doesn't match.
        """
        _validate_brief_id(brief_id)
        output = self._store.load()
        managed = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if managed is None:
            return None

        # Optimistic concurrency check
        if expected_updated_at is not None and managed.updated_at != expected_updated_at:
            raise ConcurrentModificationError(brief_id, expected_updated_at, managed.updated_at)

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

        # Persist revision to revision store
        self._revision_store.save_revision(revision)

        # Update managed brief metadata (not the head)
        managed.revision_count = new_version
        managed.latest_revision_id = revision.revision_id
        managed.updated_at = now
        managed.revision_history = managed.revision_history + [f"v{new_version}: {revision.revision_notes}"]

        self._store.save(output)

        self._audit_mutation(
            AuditEventType.BRIEF_REVISION_SAVED,
            brief_id,
            actor=AuditActor.OPERATOR,
            patch={"revision_id": revision.revision_id, "version": new_version},
            brief_snapshot=managed,
            outcome="success",
        )

        return revision

    def update_head(
        self,
        brief_id: str,
        revision_id: str,
        actor: AuditActor = AuditActor.OPERATOR,
        expected_updated_at: str | None = None,
    ) -> ManagedOpportunityBrief | None:
        """Update the current_revision_id (head) to an existing revision.

        This is how approved revisions become active.

        Raises ConcurrentModificationError if expected_updated_at doesn't match.
        """
        _validate_brief_id(brief_id)
        output = self._store.load()
        managed = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if managed is None:
            return None

        # Optimistic concurrency check
        if expected_updated_at is not None and managed.updated_at != expected_updated_at:
            raise ConcurrentModificationError(brief_id, expected_updated_at, managed.updated_at)

        now = _now_iso()
        managed.current_revision_id = revision_id
        managed.updated_at = now

        self._store.save(output)
        self._audit_mutation(
            AuditEventType.BRIEF_HEAD_UPDATED,
            brief_id,
            actor=actor,
            patch={"current_revision_id": revision_id},
            brief_snapshot=managed,
            outcome="success",
        )
        return managed

    # -------------------------------------------------------------------------
    # Lifecycle transitions
    # -------------------------------------------------------------------------

    def approve(self, brief_id: str, expected_updated_at: str | None = None) -> ManagedOpportunityBrief | None:
        """Transition a brief to the approved state."""
        return self._transition_lifecycle(brief_id, BriefLifecycleState.APPROVED, expected_updated_at)

    def archive(self, brief_id: str, expected_updated_at: str | None = None) -> ManagedOpportunityBrief | None:
        """Archive a brief."""
        return self._transition_lifecycle(brief_id, BriefLifecycleState.ARCHIVED, expected_updated_at)

    def supersede(self, brief_id: str, expected_updated_at: str | None = None) -> ManagedOpportunityBrief | None:
        """Mark a brief as superseded by a newer version."""
        return self._transition_lifecycle(brief_id, BriefLifecycleState.SUPERSEDED, expected_updated_at)

    def revert_to_draft(self, brief_id: str, expected_updated_at: str | None = None) -> ManagedOpportunityBrief | None:
        """Revert a brief back to draft state."""
        return self._transition_lifecycle(brief_id, BriefLifecycleState.DRAFT, expected_updated_at)

    def _transition_lifecycle(
        self,
        brief_id: str,
        target_state: BriefLifecycleState,
        expected_updated_at: str | None = None,
    ) -> ManagedOpportunityBrief | None:
        """Apply a lifecycle state transition.

        Raises ConcurrentModificationError if expected_updated_at doesn't match.
        """
        _validate_brief_id(brief_id)

        # Load and check concurrency
        output = self._store.load()
        managed = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if managed is None:
            return None

        if expected_updated_at is not None and managed.updated_at != expected_updated_at:
            raise ConcurrentModificationError(brief_id, expected_updated_at, managed.updated_at)

        now = _now_iso()
        updated = self._store.update_brief(
            brief_id,
            {"lifecycle_state": target_state.value, "updated_at": now},
        )
        if updated is not None:
            self._audit_mutation(
                AuditEventType.BRIEF_LIFECYCLE_CHANGED,
                brief_id,
                actor=AuditActor.OPERATOR,
                patch={"lifecycle_state": target_state.value},
                brief_snapshot=updated,
                outcome="success",
            )
        return updated

    def record_override(
        self,
        brief_id: str,
        *,
        actor_label: str,
        reason: str,
        pipeline_id: str = "",
        linked_evidence: list[str] | None = None,
    ) -> ManagedOpportunityBrief | None:
        """Attach an operator override record to the managed brief."""
        _validate_brief_id(brief_id)
        output = self._store.load()
        managed = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if managed is None:
            return None

        now = _now_iso()
        evidence = ", ".join(linked_evidence or []) if linked_evidence else "none"
        entry = (
            f"{now} | actor={actor_label or 'operator'} | "
            f"reason={reason or 'override applied'} | evidence={evidence}"
        )
        managed.override_history = [*managed.override_history, entry]
        managed.updated_at = now
        self._store.save(output)
        self._audit_mutation(
            AuditEventType.OPERATOR_OVERRIDE_APPLIED,
            brief_id,
            actor=AuditActor.OPERATOR,
            patch={
                "override_entry": entry,
                "pipeline_id": pipeline_id,
                "linked_evidence": linked_evidence or [],
            },
            brief_snapshot=managed,
            outcome="success",
        )
        return managed

    # -------------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------------

    def update_brief(
        self,
        brief_id: str,
        patch: dict[str, Any],
        expected_updated_at: str | None = None,
    ) -> ManagedOpportunityBrief | None:
        """Apply a partial brief update with timestamp management.

        Raises ConcurrentModificationError if expected_updated_at doesn't match.
        """
        _validate_brief_id(brief_id)

        # Load and check concurrency
        output = self._store.load()
        managed = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if managed is None:
            return None

        if expected_updated_at is not None and managed.updated_at != expected_updated_at:
            raise ConcurrentModificationError(brief_id, expected_updated_at, managed.updated_at)

        normalized = _normalize_brief_patch(patch)
        normalized["updated_at"] = _now_iso()
        updated = self._store.update_brief(brief_id, normalized)
        if updated is not None:
            self._audit_mutation(
                AuditEventType.BRIEF_UPDATED,
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
    # Revision access
    # -------------------------------------------------------------------------

    def get_revision(self, revision_id: str) -> BriefRevision | None:
        """Load a single brief revision by ID."""
        return self._revision_store.get_revision(revision_id)

    def list_revisions(self, brief_id: str, *, limit: int = 50) -> list[BriefRevision]:
        """List all revisions for a brief, most recent first."""
        _validate_brief_id(brief_id)
        return self._revision_store.list_revisions(brief_id, limit=limit)

    # -------------------------------------------------------------------------
    # Clone
    # -------------------------------------------------------------------------

    def clone_brief(
        self,
        brief_id: str,
        *,
        new_title: str | None = None,
    ) -> ManagedOpportunityBrief | None:
        """Create a clone of an existing brief with a new brief_id.

        The clone starts with the same current head revision but is otherwise
        independent. All revisions are copied.
        """
        _validate_brief_id(brief_id)
        output = self._store.load()
        original = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if original is None:
            return None

        now = _now_iso()
        new_brief_id = f"mbrief_{now[:10]}_{original.brief_id}_clone_{uuid4().hex[:6]}"

        # Copy current revision content
        current_revision = self._revision_store.get_revision(original.current_revision_id)
        if current_revision is None:
            return None

        # Create new revision based on current head
        new_revision = BriefRevision(
            brief_id=new_brief_id,
            version=1,
            theme=current_revision.theme,
            goal=current_revision.goal,
            primary_audience_segment=current_revision.primary_audience_segment,
            secondary_audience_segments=current_revision.secondary_audience_segments,
            problem_statements=current_revision.problem_statements,
            content_objective=current_revision.content_objective,
            proof_requirements=current_revision.proof_requirements,
            platform_constraints=current_revision.platform_constraints,
            risk_constraints=current_revision.risk_constraints,
            freshness_rationale=current_revision.freshness_rationale,
            sub_angles=current_revision.sub_angles,
            research_hypotheses=current_revision.research_hypotheses,
            success_criteria=current_revision.success_criteria,
            expert_take=current_revision.expert_take,
            non_obvious_claims_to_test=current_revision.non_obvious_claims_to_test,
            genericity_risks=current_revision.genericity_risks,
            provenance=BriefProvenance.CLONED,
            is_generated=current_revision.is_generated,
            revision_notes=f"Cloned from {brief_id} (revision {current_revision.version})",
            source_pipeline_id=current_revision.source_pipeline_id,
            created_at=now,
        )

        # Build the managed brief resource
        managed = ManagedOpportunityBrief(
            brief_id=new_brief_id,
            title=new_title or f"{original.title} (clone)",
            lifecycle_state=BriefLifecycleState.DRAFT,
            current_revision_id=new_revision.revision_id,
            latest_revision_id=new_revision.revision_id,
            revision_count=1,
            provenance=BriefProvenance.CLONED,
            created_at=now,
            updated_at=now,
            revision_history=[f"v1: {new_revision.revision_notes}"],
            operating_policies=_default_operating_policies(),
        )

        # Persist revision and brief
        self._revision_store.save_revision(new_revision)
        output.briefs.append(managed)
        self._store.save(output)

        self._audit_mutation(
            AuditEventType.BRIEF_CREATED,
            new_brief_id,
            actor=AuditActor.OPERATOR,
            patch={"source_brief_id": brief_id, "provenance": BriefProvenance.CLONED.value},
            brief_snapshot=managed,
            outcome="success",
        )

        return managed

    def branch_brief(
        self,
        brief_id: str,
        *,
        new_title: str | None = None,
        branch_reason: str = "",
    ) -> ManagedOpportunityBrief | None:
        """Create a branched copy of an existing brief for a different theme/channel.

        Unlike clone (which is for reuse), branch creates a derivative brief
        that tracks its lineage back to the source. The branched brief
        starts in DRAFT state with a copy of the current head revision.
        """
        _validate_brief_id(brief_id)
        output = self._store.load()
        original = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if original is None:
            return None

        now = _now_iso()
        new_brief_id = f"mbrief_{now[:10]}_{original.brief_id}_branch_{uuid4().hex[:6]}"

        # Copy current revision content
        current_revision = self._revision_store.get_revision(original.current_revision_id)
        if current_revision is None:
            return None

        # Create new revision based on current head
        new_revision = BriefRevision(
            brief_id=new_brief_id,
            version=1,
            theme=current_revision.theme,
            goal=current_revision.goal,
            primary_audience_segment=current_revision.primary_audience_segment,
            secondary_audience_segments=current_revision.secondary_audience_segments,
            problem_statements=current_revision.problem_statements,
            content_objective=current_revision.content_objective,
            proof_requirements=current_revision.proof_requirements,
            platform_constraints=current_revision.platform_constraints,
            risk_constraints=current_revision.risk_constraints,
            freshness_rationale=current_revision.freshness_rationale,
            sub_angles=current_revision.sub_angles,
            research_hypotheses=current_revision.research_hypotheses,
            success_criteria=current_revision.success_criteria,
            expert_take=current_revision.expert_take,
            non_obvious_claims_to_test=current_revision.non_obvious_claims_to_test,
            genericity_risks=current_revision.genericity_risks,
            provenance=BriefProvenance.BRANCHED,
            is_generated=current_revision.is_generated,
            revision_notes=f"Branched from {brief_id} (revision {current_revision.version}): {branch_reason}",
            source_pipeline_id=current_revision.source_pipeline_id,
            created_at=now,
        )

        # Build the managed brief resource with lineage tracking
        managed = ManagedOpportunityBrief(
            brief_id=new_brief_id,
            title=new_title or f"{original.title} (branch)",
            lifecycle_state=BriefLifecycleState.DRAFT,
            current_revision_id=new_revision.revision_id,
            latest_revision_id=new_revision.revision_id,
            revision_count=1,
            provenance=BriefProvenance.BRANCHED,
            created_at=now,
            updated_at=now,
            revision_history=[f"v1: {new_revision.revision_notes}"],
            source_brief_id=brief_id,
            branch_reason=branch_reason,
            operating_policies=_default_operating_policies(),
        )

        # Persist revision and brief
        self._revision_store.save_revision(new_revision)
        output.briefs.append(managed)
        self._store.save(output)

        self._audit_mutation(
            AuditEventType.BRIEF_CREATED,
            new_brief_id,
            actor=AuditActor.OPERATOR,
            patch={
                "source_brief_id": brief_id,
                "provenance": BriefProvenance.BRANCHED.value,
                "branch_reason": branch_reason,
            },
            brief_snapshot=managed,
            outcome="success",
        )

        return managed

    def list_sibling_briefs(self, brief_id: str) -> list[ManagedOpportunityBrief]:
        """List all briefs that were branched from the same source.

        Returns briefs that share the same source_brief_id.
        """
        output = self._store.load()
        source = next((b for b in output.briefs if b.brief_id == brief_id), None)
        if source is None:
            return []

        # If this brief has a source, find siblings of the same source
        # If this is a source itself, find its branches
        search_id = source.source_brief_id if source.source_brief_id else brief_id
        siblings = [
            b for b in output.briefs
            if b.source_brief_id == search_id and b.brief_id != brief_id
        ]
        return siblings

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
        self._audit_store.log_brief_mutation(
            event_type=event_type,
            brief_id=brief_id,
            actor=actor,
            patch=patch,
            brief_snapshot=brief_snapshot,
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
