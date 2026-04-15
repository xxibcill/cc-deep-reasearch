"""Migration utilities for hydrating managed briefs from legacy PipelineContext payloads.

This module provides a migration path from inline OpportunityBrief instances
(stored inside PipelineContext) into the new managed brief domain. It preserves
provenance information and handles incomplete metadata gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from cc_deep_research.content_gen.models import (
    BriefLifecycleState,
    BriefProvenance,
    BriefRevision,
    ManagedOpportunityBrief,
    OpportunityBrief,
)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass
class MigrationResult:
    """Result of a brief migration operation."""

    brief: ManagedOpportunityBrief | None
    revision: BriefRevision | None
    migration_notes: str
    is_synthetic_revision: bool = False
    """True if the original brief had no brief_id and a synthetic one was created."""
    original_brief_id: str = ""
    """The original brief_id from the OpportunityBrief, if any."""


class BriefMigration:
    """Utilities for migrating legacy briefs into the managed brief domain.

    Migration behavior
    -----------------
    - If the OpportunityBrief has a stable brief_id, it is used as the managed brief's
      brief_id (prefixed with "mbrief_" if not already).
    - If the OpportunityBrief has no brief_id (most legacy briefs), a new managed
      brief_id is generated and the original is recorded in migration_notes.
    - Each migration creates exactly one revision (v1) with provenance=IMPORTED.
    - The revision captures the full OpportunityBrief state at migration time.
    - Pipeline source information is preserved in source_pipeline_id.
    """

    @staticmethod
    def from_pipeline_context(
        pipeline_context: Any,
        *,
        source_pipeline_id: str = "",
    ) -> MigrationResult:
        """Migrate an OpportunityBrief from a PipelineContext payload.

        Parameters
        ----------
        pipeline_context : Any
            A PipelineContext instance (or dict-like) that has an
            ``opportunity_brief`` field containing an OpportunityBrief.
        source_pipeline_id : str
            The pipeline_id of the source PipelineContext.

        Returns
        -------
        MigrationResult
            The migrated brief and revision, or empty result if no brief exists.
        """
        opp_brief: OpportunityBrief | None = None

        # Handle both object and dict forms
        if hasattr(pipeline_context, "opportunity_brief"):
            opp_brief = pipeline_context.opportunity_brief
        elif isinstance(pipeline_context, dict):
            opp_brief = pipeline_context.get("opportunity_brief")

        if opp_brief is None:
            return MigrationResult(
                brief=None,
                revision=None,
                migration_notes="No opportunity_brief found in pipeline context.",
            )

        return BriefMigration.from_opportunity_brief(
            opp_brief,
            source_pipeline_id=source_pipeline_id,
        )

    @staticmethod
    def from_opportunity_brief(
        opp_brief: OpportunityBrief,
        *,
        provenance: BriefProvenance = BriefProvenance.IMPORTED,
        source_pipeline_id: str = "",
        override_brief_id: str | None = None,
    ) -> MigrationResult:
        """Migrate an OpportunityBrief into a new managed brief.

        Parameters
        ----------
        opp_brief : OpportunityBrief
            The source brief to migrate.
        provenance : BriefProvenance
            The provenance to record (default: IMPORTED for legacy briefs).
        source_pipeline_id : str
            The pipeline_id that generated this brief, if any.
        override_brief_id : str | None
            Optional brief_id to use instead of deriving from the OpportunityBrief.
            Use this when the OpportunityBrief.brief_id is unstable or empty.

        Returns
        -------
        MigrationResult
            The migrated brief and revision with full provenance.
        """
        now = _now_iso()

        # Determine brief_id
        original_brief_id = opp_brief.brief_id or ""
        is_synthetic_revision = False

        if override_brief_id:
            brief_id = override_brief_id
            migration_notes = f"Migrated with override brief_id from brief_id='{original_brief_id or '(none)'}'. "
        elif original_brief_id:
            brief_id = original_brief_id if original_brief_id.startswith("mbrief_") else f"mbrief_{original_brief_id}"
            migration_notes = f"Migrated from legacy brief with original brief_id='{original_brief_id}'. "
        else:
            # No stable brief_id - generate new one and record the original
            brief_id = f"mbrief_{now[:10]}_{opp_brief.brief_id or 'legacy'}"
            is_synthetic_revision = True
            orig_id_display = original_brief_id or "(none)"
            migration_notes = (
                f"Migrated from legacy brief with no stable brief_id. "
                f"Original brief_id='{orig_id_display}'. "
            )

        migration_notes += f"Source pipeline='{source_pipeline_id or '(none)'}'."

        # Build the revision
        revision = BriefRevision(
            brief_id=brief_id,
            version=1,
            theme=opp_brief.theme,
            goal=opp_brief.goal,
            primary_audience_segment=opp_brief.primary_audience_segment,
            secondary_audience_segments=opp_brief.secondary_audience_segments,
            problem_statements=opp_brief.problem_statements,
            content_objective=opp_brief.content_objective,
            proof_requirements=opp_brief.proof_requirements,
            platform_constraints=opp_brief.platform_constraints,
            risk_constraints=opp_brief.risk_constraints,
            freshness_rationale=opp_brief.freshness_rationale,
            sub_angles=opp_brief.sub_angles,
            research_hypotheses=opp_brief.research_hypotheses,
            success_criteria=opp_brief.success_criteria,
            expert_take=opp_brief.expert_take,
            non_obvious_claims_to_test=opp_brief.non_obvious_claims_to_test,
            genericity_risks=opp_brief.genericity_risks,
            provenance=provenance,
            is_generated=opp_brief.is_generated,
            revision_notes=f"Migrated from legacy brief. {migration_notes}",
            source_pipeline_id=source_pipeline_id,
            created_at=now,
        )

        # Build the managed brief
        managed = ManagedOpportunityBrief(
            brief_id=brief_id,
            title=opp_brief.theme or "Migrated brief",
            lifecycle_state=BriefLifecycleState.DRAFT,
            current_revision_id=revision.revision_id,
            latest_revision_id=revision.revision_id,
            revision_count=1,
            provenance=provenance,
            created_at=now,
            updated_at=now,
            revision_history=[f"v1: {revision.revision_notes}"],
        )

        return MigrationResult(
            brief=managed,
            revision=revision,
            migration_notes=migration_notes,
            is_synthetic_revision=is_synthetic_revision,
            original_brief_id=original_brief_id,
        )

    @staticmethod
    def build_migration_summary(results: list[MigrationResult]) -> dict[str, Any]:
        """Build a human-readable summary of a batch migration.

        Parameters
        ----------
        results : list[MigrationResult]
            List of migration results from a batch operation.

        Returns
        -------
        dict
            Summary with counts and migration notes.
        """
        total = len(results)
        successful = sum(1 for r in results if r.brief is not None)
        failed = total - successful
        synthetic = sum(1 for r in results if r.is_synthetic_revision)

        notes: list[str] = []
        for r in results:
            if r.brief and r.migration_notes:
                notes.append(f"  {r.brief.brief_id}: {r.migration_notes}")

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "synthetic_ids": synthetic,
            "details": notes,
        }
