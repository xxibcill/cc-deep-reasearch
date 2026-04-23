"""Route-facing API service for maintenance HTTP workflows.

This service handles HTTP-level composition (request parsing, response shaping,
error classification) while delegating domain behavior to MaintenanceStore,
MaintenanceScheduler, and BacklogService.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config, load_config
from cc_deep_research.content_gen.backlog_service import BacklogService
from cc_deep_research.content_gen.maintenance_workflow import (
    MaintenanceJobType,
    MaintenanceProposal,
    MaintenanceProposalStatus,
    MaintenanceRun,
    MaintenanceScheduler,
    MaintenanceStore,
)
from cc_deep_research.content_gen.storage import AuditActor, AuditEventType, AuditStore

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class MaintenanceApiError(Exception):
    """Base class for maintenance API errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ProposalNotFoundError(MaintenanceApiError):
    """Raised when a maintenance proposal does not exist."""

    def __init__(self, proposal_id: str) -> None:
        super().__init__(f"Proposal not found: {proposal_id}", status_code=404)


class UnknownJobTypeError(MaintenanceApiError):
    """Raised when an unknown maintenance job type is provided."""

    def __init__(self, job_type: str) -> None:
        super().__init__(f"Unknown job type: {job_type}", status_code=400)


class MaintenanceApiService:
    """API-level service for maintenance HTTP request handling.

    This class handles HTTP-specific concerns:
    - Request validation and parsing
    - Response shaping (serialization)
    - Error classification and mapping
    - HTTP workflow composition

    Domain behavior is delegated to MaintenanceStore, MaintenanceScheduler,
    BacklogService, and AuditStore.
    """

    def __init__(
        self,
        config: Config | None = None,
        maintenance_store: MaintenanceStore | None = None,
        backlog_service: BacklogService | None = None,
        scheduler: MaintenanceScheduler | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self._config = config or load_config()
        self._maintenance_store = maintenance_store or MaintenanceStore(config=self._config)
        self._backlog_service = backlog_service or BacklogService(self._config)
        self._scheduler = scheduler
        self._audit_store = audit_store or AuditStore(config=self._config)

    @property
    def path(self) -> Path:
        """Return the maintenance store path."""
        return self._maintenance_store._proposals_path

    # ------------------------------------------------------------------
    # Proposals
    # ------------------------------------------------------------------

    def list_proposals(
        self,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """List maintenance proposals with optional filtering.

        Args:
            status: Optional status filter (pending, approved, rejected, applied, expired).
            job_type: Optional job type filter.
            limit: Maximum number of proposals to return.

        Returns:
            Tuple of (proposals_list, count).
        """
        status_enum = MaintenanceProposalStatus(status) if status else None
        job_type_enum = MaintenanceJobType(job_type) if job_type else None
        proposals = self._maintenance_store.load_proposals(
            status=status_enum,
            job_type=job_type_enum,
            limit=limit,
        )
        return [p.to_dict() for p in proposals], len(proposals)

    def resolve_proposal(
        self,
        proposal_id: str,
        decision: str,
    ) -> dict[str, Any]:
        """Resolve a maintenance proposal (approve or reject).

        If approved, the suggested_patch is applied to the affected backlog items.

        Args:
            proposal_id: ID of the proposal to resolve.
            decision: "approved" or "rejected".

        Returns:
            The resolved proposal as a dict.

        Raises:
            ProposalNotFoundError: If proposal doesn't exist.
        """
        proposal = self._maintenance_store.resolve_proposal(proposal_id, decision=decision)
        if proposal is None:
            raise ProposalNotFoundError(proposal_id)

        # Apply approved proposals to backlog items
        if decision == "approved" and proposal.suggested_patch:
            for idea_id in proposal.affected_idea_ids:
                self._backlog_service.update_item(idea_id, dict(proposal.suggested_patch))

        # Log to audit
        for idea_id in proposal.affected_idea_ids:
            self._audit_store.log_backlog_mutation(
                event_type=AuditEventType.MAINTENANCE_PROPOSAL,
                idea_id=idea_id,
                actor=AuditActor.OPERATOR,
                patch={"proposal_id": proposal_id, "decision": decision},
                outcome=decision,
            )

        return proposal.to_dict()

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def trigger_job(
        self,
        job_type: str,
        scheduler: MaintenanceScheduler | None = None,
    ) -> dict[str, Any]:
        """Trigger a maintenance job immediately (on-demand).

        Args:
            job_type: Job type string (stale_item_review, gap_summary, etc.).
            scheduler: Optional scheduler to use. If not provided, creates a new one.

        Returns:
            Dict with run details, proposals generated, outcome, and error.

        Raises:
            UnknownJobTypeError: If job_type is not recognized.
        """
        try:
            job_type_enum = MaintenanceJobType(job_type)
        except ValueError:
            raise UnknownJobTypeError(job_type) from None

        active_scheduler = scheduler or self._scheduler or MaintenanceScheduler(config=self._config)
        run = active_scheduler.trigger_job(job_type_enum)

        return {
            "run": run.to_dict(),
            "proposals_generated": run.proposals_count,
            "outcome": run.outcome,
            "error": run.error or None,
        }

    def list_runs(self, limit: int = 20) -> tuple[list[dict[str, Any]], int]:
        """List recent maintenance run records.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            Tuple of (runs_list, count).
        """
        runs = self._maintenance_store.load_runs(limit=limit)
        return [r.to_dict() for r in runs], len(runs)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_proposal(proposal: MaintenanceProposal | dict[str, Any]) -> dict[str, Any]:
        """Serialize a proposal to JSON-compatible dict."""
        if isinstance(proposal, dict):
            return proposal
        return proposal.to_dict()

    @staticmethod
    def serialize_run(run: MaintenanceRun | dict[str, Any]) -> dict[str, Any]:
        """Serialize a run to JSON-compatible dict."""
        if isinstance(run, dict):
            return run
        return run.to_dict()
