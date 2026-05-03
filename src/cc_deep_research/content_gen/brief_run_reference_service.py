"""Managed brief and run-reference service extracted from legacy_orchestrator.

This module provides ``BriefRunReferenceService``, which owns the managed-brief
and run-reference logic extracted from ``ContentGenOrchestrator``.
``ContentGenOrchestrator`` methods are preserved as thin compatibility
wrappers that delegate to this service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.models import (
    BriefExecutionGate,
    BriefExecutionPolicyMode,
    BriefLifecycleState,
    BriefProvenance,
    ManagedOpportunityBrief,
    OpportunityBrief,
    PipelineBriefReference,
    PipelineContext,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config

__all__ = ["BriefRunReferenceService"]


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(tz=UTC).isoformat()


class BriefRunReferenceService:
    """Owns managed-brief and run-reference logic.

    This service replaces the deprecated ``ContentGenOrchestrator`` for all
    brief-related operations. It is importable without pulling in legacy
    stage handlers.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._store: Any = None

    def _get_service(self) -> Any:
        if self._store is None:
            from cc_deep_research.content_gen.brief_service import BriefService

            self._store = BriefService(config=self._config)
        return self._store

    # ------------------------------------------------------------------
    # Brief reference establishment
    # ------------------------------------------------------------------

    def establish_brief_reference(
        self,
        *,
        brief_id: str | None = None,
        managed_brief: ManagedOpportunityBrief | None = None,
        revision_id: str | None = None,
        revision_version: int | None = None,
        snapshot: OpportunityBrief | None = None,
        reference_type: str = "managed",
        seeded_from_revision_id: str = "",
    ) -> PipelineBriefReference:
        """Establish a brief reference from a managed brief or inline data."""
        if managed_brief is not None:
            resolved_brief_id = brief_id or managed_brief.brief_id
            resolved_revision_id = (
                revision_id or managed_brief.current_revision_id or managed_brief.latest_revision_id
            )
            resolved_version = revision_version or managed_brief.revision_count
            resolved_state = managed_brief.lifecycle_state
            resolved_snapshot = snapshot or self._build_brief_snapshot(managed_brief)
            resolved_type = reference_type
        else:
            resolved_brief_id = brief_id or ""
            resolved_revision_id = revision_id or ""
            resolved_version = revision_version or 0
            resolved_state = BriefLifecycleState.DRAFT
            resolved_snapshot = snapshot
            resolved_type = "inline_fallback"

        return PipelineBriefReference(
            brief_id=resolved_brief_id,
            revision_id=resolved_revision_id,
            revision_version=resolved_version,
            snapshot=resolved_snapshot,
            lifecycle_state=resolved_state,
            reference_type=resolved_type,
            seeded_from_revision_id=seeded_from_revision_id,
            created_at=_utc_now(),
        )

    def _build_brief_snapshot(self, managed: ManagedOpportunityBrief) -> OpportunityBrief:
        """Build an OpportunityBrief snapshot from a managed brief's current head."""
        return OpportunityBrief(
            brief_id=managed.brief_id,
            theme=managed.title,
            goal="",
            version=managed.revision_count,
            is_generated=True,
            is_approved=(managed.lifecycle_state == BriefLifecycleState.APPROVED),
        )

    # ------------------------------------------------------------------
    # Brief resolution for runs
    # ------------------------------------------------------------------

    def get_brief_for_run(
        self,
        *,
        brief_id: str | None = None,
        revision_id: str | None = None,
        snapshot: OpportunityBrief | None = None,
    ) -> tuple[PipelineBriefReference, OpportunityBrief | None]:
        """Get the brief reference and resolved brief content for starting a run."""
        if not brief_id:
            ref = self.establish_brief_reference(
                snapshot=snapshot, reference_type="inline_fallback"
            )
            return ref, snapshot

        store = self._get_service()
        managed = store.get_brief(brief_id)

        if managed is None:
            ref = self.establish_brief_reference(
                brief_id=brief_id,
                snapshot=snapshot,
                reference_type="inline_fallback" if snapshot else "imported",
            )
            return ref, snapshot

        target_revision_id = (
            revision_id or managed.current_revision_id or managed.latest_revision_id
        )

        ref = self.establish_brief_reference(
            brief_id=managed.brief_id,
            managed_brief=managed,
            revision_id=target_revision_id,
            seeded_from_revision_id=target_revision_id if revision_id else "",
        )

        brief_content = self._load_brief_revision_content(managed, target_revision_id) or snapshot

        return ref, brief_content

    def _load_brief_revision_content(
        self,
        managed: ManagedOpportunityBrief,
        revision_id: str,
    ) -> OpportunityBrief | None:
        """Load the OpportunityBrief content for a specific revision."""
        store = self._get_service()
        revision = store.get_revision(revision_id)
        if revision is None:
            return None

        return OpportunityBrief(
            brief_id=managed.brief_id,
            theme=revision.theme,
            goal=revision.goal,
            primary_audience_segment=revision.primary_audience_segment,
            secondary_audience_segments=revision.secondary_audience_segments,
            problem_statements=revision.problem_statements,
            content_objective=revision.content_objective,
            proof_requirements=revision.proof_requirements,
            platform_constraints=revision.platform_constraints,
            risk_constraints=revision.risk_constraints,
            freshness_rationale=revision.freshness_rationale,
            sub_angles=revision.sub_angles,
            research_hypotheses=revision.research_hypotheses,
            success_criteria=revision.success_criteria,
            expert_take=revision.expert_take,
            non_obvious_claims_to_test=revision.non_obvious_claims_to_test,
            genericity_risks=revision.genericity_risks,
            is_generated=revision.is_generated,
        )

    def get_brief_revisions_info(
        self,
        brief_id: str,
    ) -> dict[str, Any] | None:
        """Get information about available revisions for a managed brief."""
        store = self._get_service()
        managed = store.get_brief(brief_id)

        if managed is None:
            return None

        return {
            "brief_id": managed.brief_id,
            "title": managed.title,
            "lifecycle_state": managed.lifecycle_state.value,
            "current_revision_id": managed.current_revision_id,
            "latest_revision_id": managed.latest_revision_id,
            "revision_count": managed.revision_count,
            "revision_history": managed.revision_history,
            "created_at": managed.created_at,
            "updated_at": managed.updated_at,
            "provenance": managed.provenance.value,
        }

    def create_seeded_run_reference(
        self,
        brief_id: str,
        *,
        revision_id: str | None = None,
        revision_version: int | None = None,
        snapshot: OpportunityBrief | None = None,
    ) -> PipelineBriefReference | None:
        """Create a brief reference for starting a new run from a specific revision."""
        if not brief_id:
            return None

        store = self._get_service()
        managed = store.get_brief(brief_id)

        if managed is None:
            return None

        target_revision_id = (
            revision_id or managed.current_revision_id or managed.latest_revision_id
        )

        return self.establish_brief_reference(
            brief_id=brief_id,
            managed_brief=managed,
            revision_id=target_revision_id,
            revision_version=revision_version or managed.revision_count,
            snapshot=snapshot,
            reference_type="managed",
            seeded_from_revision_id=target_revision_id,
        )

    def create_clone_reference(
        self,
        source_brief_id: str,
        *,
        source_revision_id: str | None = None,
        snapshot: OpportunityBrief | None = None,
    ) -> tuple[PipelineBriefReference, str | None]:
        """Create a brief reference by cloning from an existing brief."""
        if not source_brief_id:
            return None, None

        store = self._get_service()
        source = store.get_brief(source_brief_id)

        if source is None:
            return None, None

        source_rev_id = (
            source_revision_id or source.current_revision_id or source.latest_revision_id
        )

        if snapshot is None:
            snapshot = self._build_brief_snapshot(source)

        new_brief = store.create_from_opportunity(
            snapshot,
            provenance=BriefProvenance.CLONED,
            source_pipeline_id="",
            revision_notes=f"Cloned from brief '{source_brief_id}' revision '{source_rev_id}'",
        )

        ref = self.establish_brief_reference(
            brief_id=new_brief.brief_id,
            managed_brief=new_brief,
            revision_id=new_brief.current_revision_id,
            snapshot=snapshot,
            reference_type="managed",
        )

        return ref, new_brief.brief_id

    # ------------------------------------------------------------------
    # Brief execution gates
    # ------------------------------------------------------------------

    def initialize_brief_gate(
        self,
        *,
        brief_state: BriefLifecycleState = BriefLifecycleState.DRAFT,
        policy_mode: BriefExecutionPolicyMode | None = None,
    ) -> BriefExecutionGate:
        """Initialize the brief execution gate for a pipeline run."""
        if policy_mode is None:
            policy_mode = self.get_default_gate_policy()

        gate = BriefExecutionGate(
            policy_mode=policy_mode,
            brief_state_at_start=brief_state,
        )

        can_proceed, message = gate.check_gate(brief_state, "plan_opportunity")
        if not can_proceed:
            gate.was_blocked = True
            gate.error_message = message
        elif brief_state == BriefLifecycleState.DRAFT:
            gate.warnings.append(
                f"Pipeline starting with {brief_state.value} brief. "
                f"Consider approving before running production stages."
            )

        return gate

    def get_default_gate_policy(self) -> BriefExecutionPolicyMode:
        """Get the default gate policy from config."""
        try:
            gate_policy = getattr(self._config.content_gen, "brief_gate_policy", None)
            if gate_policy:
                return BriefExecutionPolicyMode(gate_policy)
        except (ValueError, AttributeError):
            pass
        return BriefExecutionPolicyMode.DEFAULT_APPROVED

    def check_stage_gate(
        self,
        ctx: PipelineContext,
        stage_name: str,
    ) -> tuple[bool, str]:
        """Check if execution can proceed for the given stage."""
        brief_state = BriefLifecycleState.DRAFT
        if ctx.brief_reference is not None:
            brief_state = ctx.brief_reference.lifecycle_state
        else:
            pass

        gate = ctx.brief_gate
        if gate is None:
            return True, "No brief gate configured."

        return gate.check_gate(brief_state, stage_name)

    def get_gate_status_message(self, ctx: PipelineContext) -> str:
        """Format a human-readable gate status message."""
        gate = ctx.brief_gate
        if gate is None:
            return "No brief gate configured."
        if not gate.was_blocked:
            return "Brief gate is open."
        return f"Brief gate is blocked: {gate.error_message}"
