"""Service layer for Opportunity Radar.

RadarService wraps the RadarStore with business-logic operations that are
meaningful to routes and the opportunity engine. Service methods return typed
models and handle cross-entity operations (e.g., creating an opportunity
with its initial score, linking signals).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

from cc_deep_research.radar.models import (
    AlertMute,
    FeedbackType,
    FreshnessState,
    Opportunity,
    OpportunityFeedback,
    OpportunityScore,
    OpportunityStatus,
    OpportunityType,
    RadarAlert,
    RadarDigest,
    RadarSource,
    RawSignal,
    ScanJob,
    ScoringFeedback,
    SourceStatus,
    StatusHistoryEntry,
    WorkflowLink,
    WorkflowType,
)
from cc_deep_research.radar.storage import RadarStore

if TYPE_CHECKING:
    pass


TEnum = TypeVar("TEnum", bound=Enum)


def _coerce_optional_enum(
    value: str | TEnum | None,
    enum_cls: type[TEnum],
) -> TEnum | None:
    """Return *value* as *enum_cls* when provided."""
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    return enum_cls(value)


class RadarService:
    """Service layer for Radar business logic.

    This service wraps RadarStore to provide:
    - Typed service methods for routes and engine code
    - Cross-entity operations (create opportunity + score + links)
    - Status and feedback transitions
    - Workflow conversion links
    """

    def __init__(self, store: RadarStore | None = None) -> None:
        """Initialize the service with an optional store."""
        self._store = store or RadarStore()

    # -- Source operations ----------------------------------------------------

    def create_source(
        self,
        source_type: str,
        label: str,
        url_or_identifier: str,
        *,
        scan_cadence: str = "6h",
        metadata: dict[str, Any] | None = None,
    ) -> RadarSource:
        """Create and persist a new RadarSource.

        Args:
            source_type: Type of source (news, blog, changelog, etc.).
            label: Human-readable label.
            url_or_identifier: URL or other identifier.
            scan_cadence: How often to scan (e.g., "1h", "6h", "1d").
            metadata: Additional source configuration.

        Returns:
            The created RadarSource.
        """
        from cc_deep_research.radar.models import SourceType

        source = RadarSource(
            source_type=SourceType(source_type),
            label=label,
            url_or_identifier=url_or_identifier,
            scan_cadence=scan_cadence,
            metadata=metadata or {},
        )
        self._store.add_source(source)
        return source

    def list_sources(
        self,
        status: str | SourceStatus | None = None,
    ) -> list[RadarSource]:
        """List all sources, optionally filtered by status.

        Args:
            status: Optional status to filter by (active, inactive, error).

        Returns:
            List of RadarSource records.
        """
        sources = self._store.load_sources().sources
        status_enum = _coerce_optional_enum(status, SourceStatus)
        if status_enum is not None:
            sources = [s for s in sources if s.status == status_enum]
        return sources

    def get_source(self, source_id: str) -> RadarSource | None:
        """Get a single source by id."""
        return self._store.get_source(source_id)

    def update_source_status(
        self,
        source_id: str,
        status: str,
    ) -> RadarSource | None:
        """Update the status of a source.

        Args:
            source_id: The source to update.
            status: New status (active, inactive, error).

        Returns:
            Updated RadarSource or None if not found.
        """
        from cc_deep_research.radar.models import SourceStatus

        return self._store.update_source(source_id, {"status": SourceStatus(status)})

    # -- Signal operations ----------------------------------------------------

    def add_signal(
        self,
        source_id: str,
        title: str,
        *,
        external_id: str | None = None,
        summary: str | None = None,
        url: str | None = None,
        published_at: str | None = None,
        content_hash: str | None = None,
        normalized_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RawSignal:
        """Add a raw signal and persist it.

        Args:
            source_id: The source this signal came from.
            title: Normalized title.
            external_id: Original id from the source.
            summary: Short summary or snippet.
            url: URL to the original item.
            published_at: ISO timestamp of original publication.
            content_hash: Hash to detect duplicates.
            normalized_type: Source-specific type classification.
            metadata: Additional signal data.

        Returns:
            The created RawSignal.
        """
        signal = RawSignal(
            source_id=source_id,
            title=title,
            external_id=external_id,
            summary=summary,
            url=url,
            published_at=published_at,
            content_hash=content_hash,
            normalized_type=normalized_type,
            metadata=metadata or {},
        )
        self._store.add_signal(signal)
        return signal

    # -- Opportunity operations -----------------------------------------------

    def create_opportunity(
        self,
        title: str,
        summary: str,
        opportunity_type: str,
        *,
        why_it_matters: str | None = None,
        recommended_action: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Opportunity:
        """Create and persist a new Opportunity.

        Args:
            title: Short actionable title.
            summary: Concise description.
            opportunity_type: Category of opportunity.
            why_it_matters: Strategic significance explanation.
            recommended_action: Suggested next step.
            metadata: Additional opportunity data.

        Returns:
            The created Opportunity.
        """
        opp = Opportunity(
            title=title,
            summary=summary,
            opportunity_type=OpportunityType(opportunity_type),
            why_it_matters=why_it_matters,
            recommended_action=recommended_action,
            metadata=metadata or {},
        )
        self._store.add_opportunity(opp)
        return opp

    def list_opportunities(
        self,
        status: str | OpportunityStatus | None = None,
        opportunity_type: str | OpportunityType | None = None,
        freshness: str | FreshnessState | None = None,
        limit: int | None = None,
    ) -> list[Opportunity]:
        """List opportunities with optional filtering.

        Args:
            status: Filter by OpportunityStatus value.
            opportunity_type: Filter by OpportunityType value.
            freshness: Filter by FreshnessState value.
            limit: Maximum number to return.

        Returns:
            Filtered, sorted list of opportunities.
        """
        status_enum = _coerce_optional_enum(status, OpportunityStatus)
        type_enum = _coerce_optional_enum(opportunity_type, OpportunityType)
        freshness_enum = _coerce_optional_enum(freshness, FreshnessState)
        return self._store.list_opportunities(
            status=status_enum,
            opportunity_type=type_enum,
            freshness=freshness_enum,
            limit=limit,
        )

    def get_opportunity_detail(
        self,
        opportunity_id: str,
    ) -> dict[str, Any] | None:
        """Get full detail for an opportunity including signals and score.

        Args:
            opportunity_id: The opportunity to retrieve.

        Returns:
            Dict with opportunity, score, signal links, and feedback or None.
        """
        opp = self._store.get_opportunity(opportunity_id)
        if opp is None:
            return None

        score = self._store.get_score(opportunity_id)
        signal_ids = self._store.get_signal_ids_for_opportunity(opportunity_id)
        signals = [self._store.get_signal(sid) for sid in signal_ids if sid]
        signals = [s for s in signals if s is not None]
        feedback = self._store.get_feedback_for_opportunity(opportunity_id)
        workflow_links = self._store.get_workflow_links_for_opportunity(opportunity_id)

        return {
            "opportunity": opp,
            "score": score,
            "signals": signals,
            "feedback": feedback,
            "workflow_links": workflow_links,
        }

    def update_opportunity_status(
        self,
        opportunity_id: str,
        status: str,
        *,
        reason: str | None = None,
    ) -> Opportunity | None:
        """Update the status of an opportunity.

        Also records the status change in the history log.

        Args:
            opportunity_id: The opportunity to update.
            status: New status value.
            reason: Optional reason for the change.

        Returns:
            Updated Opportunity or None if not found.
        """
        opp = self._store.get_opportunity(opportunity_id)
        if opp is None:
            return None

        previous_status = opp.status
        new_status = OpportunityStatus(status)

        # Record history entry
        history_entry = StatusHistoryEntry(
            opportunity_id=opportunity_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
        )
        self._store.add_status_history_entry(history_entry)

        return self._store.update_opportunity(
            opportunity_id,
            {"status": new_status},
        )

    # -- Score operations ----------------------------------------------------

    def save_score(
        self,
        opportunity_id: str,
        strategic_relevance_score: float,
        novelty_score: float,
        urgency_score: float,
        evidence_score: float,
        business_value_score: float,
        workflow_fit_score: float,
        *,
        explanation: str | None = None,
    ) -> OpportunityScore:
        """Compute and persist the total score for an opportunity.

        Uses fixed weights: StrategicRelevance 30%, BusinessValue 20%,
        Urgency 15%, Evidence 15%, Novelty 10%, WorkflowFit 10%.

        Args:
            opportunity_id: The opportunity to score.
            strategic_relevance_score: Strategy fit score (0-100).
            novelty_score: How new this is (0-100).
            urgency_score: Time sensitivity (0-100).
            evidence_score: Credibility and support (0-100).
            business_value_score: Expected value (0-100).
            workflow_fit_score: Actionability (0-100).
            explanation: Human-readable score explanation.

        Returns:
            The computed OpportunityScore.
        """
        total = (
            strategic_relevance_score * 0.30
            + novelty_score * 0.10
            + urgency_score * 0.15
            + evidence_score * 0.15
            + business_value_score * 0.20
            + workflow_fit_score * 0.10
        )

        score = OpportunityScore(
            opportunity_id=opportunity_id,
            strategic_relevance_score=strategic_relevance_score,
            novelty_score=novelty_score,
            urgency_score=urgency_score,
            evidence_score=evidence_score,
            business_value_score=business_value_score,
            workflow_fit_score=workflow_fit_score,
            total_score=total,
            explanation=explanation,
        )
        self._store.upsert_score(score)

        # Also update the opportunity's total_score and priority_label
        self._store.update_opportunity(opportunity_id, {
            "total_score": total,
            "priority_label": score.priority_label,
        })

        return score

    # -- Feedback operations ------------------------------------------------

    def record_feedback(
        self,
        opportunity_id: str,
        feedback_type: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> OpportunityFeedback:
        """Record user feedback on an opportunity.

        Args:
            opportunity_id: The opportunity feedback relates to.
            feedback_type: Type of feedback action.
            metadata: Additional feedback context.

        Returns:
            The created OpportunityFeedback.
        """
        feedback = OpportunityFeedback(
            opportunity_id=opportunity_id,
            feedback_type=FeedbackType(feedback_type),
            metadata=metadata or {},
        )
        self._store.add_feedback(feedback)
        return feedback

    # -- Workflow link operations ---------------------------------------------

    def link_workflow(
        self,
        opportunity_id: str,
        workflow_type: str,
        workflow_id: str,
    ) -> WorkflowLink:
        """Link an opportunity to a downstream workflow.

        Args:
            opportunity_id: The opportunity that triggered the workflow.
            workflow_type: Type of workflow (research_run, brief, etc.).
            workflow_id: Identifier of the created workflow object.

        Returns:
            The created WorkflowLink.
        """
        link = WorkflowLink(
            opportunity_id=opportunity_id,
            workflow_type=WorkflowType(workflow_type),
            workflow_id=workflow_id,
        )
        self._store.add_workflow_link(link)
        return link

    # -- Status history operations --------------------------------------------

    def get_status_history(self, opportunity_id: str) -> list[StatusHistoryEntry]:
        """Get the status history for an opportunity.

        Args:
            opportunity_id: The opportunity to get history for.

        Returns:
            List of status history entries, oldest first.
        """
        entries = self._store.get_status_history_for_opportunity(opportunity_id)
        entries.sort(key=lambda e: e.changed_at)
        return entries

    # -- Workflow launch helpers ----------------------------------------------

    def get_opportunity_context_for_research(
        self,
        opportunity_id: str,
    ) -> dict[str, Any] | None:
        """Build a research query from opportunity context.

        Extracts title, summary, and why_it_matters to construct
        a research query that can be used to launch a research run.

        Args:
            opportunity_id: The opportunity to build context from.

        Returns:
            Dict with query, title, summary, why_it_matters, or None if not found.
        """
        opp = self._store.get_opportunity(opportunity_id)
        if opp is None:
            return None

        # Build research query from opportunity context
        query_parts = [opp.title]
        if opp.summary:
            query_parts.append(f": {opp.summary}")
        if opp.why_it_matters:
            query_parts.append(f" - {opp.why_it_matters}")

        return {
            "query": "".join(query_parts),
            "title": opp.title,
            "summary": opp.summary,
            "why_it_matters": opp.why_it_matters,
            "recommended_action": opp.recommended_action,
            "opportunity_type": opp.opportunity_type.value,
            "total_score": opp.total_score,
        }

    def get_opportunity_context_for_brief(
        self,
        opportunity_id: str,
    ) -> dict[str, Any] | None:
        """Build brief context from opportunity.

        Args:
            opportunity_id: The opportunity to build context from.

        Returns:
            Dict with title, topic, context, or None if not found.
        """
        opp = self._store.get_opportunity(opportunity_id)
        if opp is None:
            return None

        return {
            "title": opp.title,
            "topic": opp.summary,
            "context": opp.why_it_matters or "",
            "opportunity_type": opp.opportunity_type.value,
            "recommended_action": opp.recommended_action,
        }

    def get_opportunity_context_for_backlog(
        self,
        opportunity_id: str,
    ) -> dict[str, Any] | None:
        """Build backlog item context from opportunity.

        Args:
            opportunity_id: The opportunity to build context from.

        Returns:
            Dict with title, one_liner, raw_idea, why_now, or None if not found.
        """
        opp = self._store.get_opportunity(opportunity_id)
        if opp is None:
            return None

        return {
            "title": opp.title,
            "one_liner": opp.summary,
            "raw_idea": f"{opp.summary}\n\n{opp.why_it_matters or ''}".strip(),
            "why_now": opp.recommended_action or "",
            "opportunity_id": opportunity_id,
        }

    # -- Source governance ----------------------------------------------------

    def update_source(
        self,
        source_id: str,
        patch: dict[str, Any],
    ) -> RadarSource | None:
        """Update source fields including governance metadata.

        Args:
            source_id: The source to update.
            patch: Fields to update.

        Returns:
            Updated RadarSource or None if not found.
        """
        return self._store.update_source(source_id, patch)

    def get_source_health(self, source_id: str) -> dict[str, Any] | None:
        """Get computed health details for a source.

        Returns health state, failure count, last failure reason, and scan history.
        """
        source = self._store.get_source(source_id)
        if source is None:
            return None

        recent_jobs = self._store.get_scan_jobs_for_source(source_id, limit=5)
        return {
            "source_id": source_id,
            "health": source.health.value,
            "consecutive_failures": source.consecutive_failures,
            "last_failure_reason": source.last_failure_reason,
            "last_scan_success": source.last_scan_success,
            "last_scanned_at": source.last_scanned_at,
            "recent_jobs": [
                {
                    "id": j.id,
                    "status": j.status.value,
                    "signals_found": j.signals_found,
                    "started_at": j.started_at,
                    "completed_at": j.completed_at,
                }
                for j in recent_jobs
            ],
        }

    def list_sources_by_health(
        self,
        health: str | None = None,
        priority: str | None = None,
        owner: str | None = None,
    ) -> list[RadarSource]:
        """List sources filtered by governance attributes.

        Args:
            health: Filter by health state (healthy, degraded, unhealthy).
            priority: Filter by priority (critical, high, medium, low).
            owner: Filter by owner.

        Returns:
            Filtered list of sources.
        """
        from cc_deep_research.radar.models import SourceHealth, SourcePriority

        sources = self._store.load_sources().sources

        if health is not None:
            sources = [s for s in sources if s.health == SourceHealth(health)]
        if priority is not None:
            sources = [s for s in sources if s.priority == SourcePriority(priority)]
        if owner is not None:
            sources = [s for s in sources if s.owner == owner]

        return sources

    # -- Scan job operations --------------------------------------------------

    def create_scan_job(
        self,
        source_id: str | None = None,
        triggered_by: str = "schedule",
        scan_type: str = "full",
    ) -> ScanJob:
        """Create and start a scan job.

        Returns None if a scan is already pending/running for this source.
        """
        if source_id is not None:
            existing = self._store.get_pending_scan_job(source_id)
            if existing is not None:
                return existing  # Prevent overlapping scans

        job = ScanJob(
            source_id=source_id,
            triggered_by=triggered_by,
            scan_type=scan_type,
            status="pending",
        )
        self._store.add_scan_job(job)
        return job

    def start_scan_job(self, job_id: str) -> ScanJob | None:
        """Mark a scan job as running."""
        return self._store.update_scan_job(job_id, {"status": "running"})

    def complete_scan_job(
        self,
        job_id: str,
        signals_found: int = 0,
        errors: list[str] | None = None,
    ) -> ScanJob | None:
        """Mark a scan job as completed."""
        return self._store.update_scan_job(
            job_id,
            {
                "status": "completed",
                "signals_found": signals_found,
                "errors": errors or [],
            },
        )

    def fail_scan_job(self, job_id: str, error: str) -> ScanJob | None:
        """Mark a scan job as failed."""
        return self._store.update_scan_job(
            job_id,
            {
                "status": "failed",
                "errors": [error],
            },
        )

    def skip_scan_job(self, job_id: str, reason: str) -> ScanJob | None:
        """Mark a scan job as skipped."""
        return self._store.update_scan_job(
            job_id,
            {
                "status": "skipped",
                "errors": [reason],
            },
        )

    def run_scan_now(self, source_id: str) -> ScanJob:
        """Run a scan immediately for a source, bypassing cadence."""
        job = self.create_scan_job(source_id, triggered_by="manual", scan_type="full")
        return job

    def dry_run_scan(self, source_id: str | None = None) -> dict[str, Any]:
        """Preview which sources would be scanned without executing.

        Args:
            source_id: Specific source to preview (None for all due).

        Returns:
            Dict with sources that would be scanned and job count.
        """
        if source_id is not None:
            source = self._store.get_source(source_id)
            if source is None:
                return {"sources": [], "job_count": 0, "dry_run": True}
            sources = [source] if source.status.value == "active" else []
        else:
            sources = [s for s in self._store.load_sources().sources if s.status.value == "active"]

        from cc_deep_research.radar.scanner import is_due_for_scan

        due_sources = [s for s in sources if is_due_for_scan(s)]
        return {
            "sources": [{"id": s.id, "label": s.label, "scan_cadence": s.scan_cadence} for s in due_sources],
            "job_count": len(due_sources),
            "dry_run": True,
        }

    def get_scan_history(self, source_id: str | None = None, limit: int = 50) -> list[ScanJob]:
        """Get scan job history.

        Args:
            source_id: Filter to a specific source (None for all).
            limit: Maximum number of jobs to return.

        Returns:
            List of scan jobs, most recent first.
        """
        if source_id is not None:
            return self._store.get_scan_jobs_for_source(source_id, limit=limit)
        return self._store.get_recent_scan_jobs(limit=limit)

    def pause_source_schedule(self, source_id: str) -> RadarSource | None:
        """Pause scheduled scanning for a source."""
        return self._store.update_source(source_id, {"status": "inactive"})

    def resume_source_schedule(self, source_id: str) -> RadarSource | None:
        """Resume scheduled scanning for a source."""
        return self._store.update_source(source_id, {"status": "active"})

    # -- Alert operations -----------------------------------------------------

    def create_alert(
        self,
        trigger: str,
        title: str,
        message: str,
        severity: str = "info",
        source_id: str | None = None,
        opportunity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RadarAlert:
        """Create an alert if not muted."""
        from cc_deep_research.radar.models import AlertSeverity, AlertTrigger

        trigger_enum = AlertTrigger(trigger)
        if self._store.is_alert_muted(trigger, source_id):
            return None  # Silently skip muted alerts

        alert = RadarAlert(
            trigger=trigger_enum,
            severity=AlertSeverity(severity),
            title=title,
            message=message,
            source_id=source_id,
            opportunity_id=opportunity_id,
            metadata=metadata or {},
        )
        self._store.add_alert(alert)
        return alert

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> RadarAlert | None:
        """Acknowledge an alert."""
        return self._store.acknowledge_alert(alert_id, acknowledged_by)

    def get_unacknowledged_alerts(self) -> list[RadarAlert]:
        """Get all unacknowledged alerts."""
        return self._store.get_unacknowledged_alerts()

    def mute_alert(
        self,
        trigger: str,
        source_id: str | None = None,
        muted_by: str | None = None,
        expires_at: str | None = None,
    ) -> AlertMute:
        """Mute an alert trigger."""
        from cc_deep_research.radar.models import AlertTrigger

        mute = AlertMute(
            trigger=AlertTrigger(trigger),
            source_id=source_id,
            muted_by=muted_by,
            expires_at=expires_at,
        )
        self._store.add_alert_mute(mute)
        return mute

    def unmute_alert(self, mute_id: str) -> bool:
        """Remove an alert mute."""
        return self._store.remove_alert_mute(mute_id)

    def get_alert_mutes(self) -> list[AlertMute]:
        """Get all active alert mutes."""
        return self._store.load_alert_mutes().mutes

    # -- Digest operations ---------------------------------------------------

    def generate_digest(
        self,
        period_start: str,
        period_end: str,
    ) -> RadarDigest:
        """Generate a digest summarizing radar activity in the period."""
        # Get new opportunities in period
        all_opps = self._store.load_opportunities().opportunities
        period_opps = [
            o for o in all_opps
            if period_start <= o.created_at <= period_end
        ]
        period_opps.sort(key=lambda o: -o.total_score)
        top_opps = [
            {
                "id": o.id,
                "title": o.title,
                "score": o.total_score,
                "type": o.opportunity_type.value,
            }
            for o in period_opps[:10]
        ]

        # Get source health issues
        sources = self._store.load_sources().sources
        health_issues = [
            {
                "id": s.id,
                "label": s.label,
                "health": s.health.value,
                "consecutive_failures": s.consecutive_failures,
                "last_failure_reason": s.last_failure_reason,
            }
            for s in sources
            if s.health.value in ("degraded", "unhealthy")
        ]

        # Get alert count in period
        alerts = self._store.load_alerts().alerts
        alert_count = sum(1 for a in alerts if period_start <= a.created_at <= period_end)

        digest = RadarDigest(
            period_start=period_start,
            period_end=period_end,
            new_opportunities_count=len(period_opps),
            top_opportunities=top_opps,
            source_health_issues=health_issues,
            alert_count=alert_count,
        )
        self._store.add_digest(digest)
        return digest

    def get_recent_digests(self, limit: int = 12) -> list[RadarDigest]:
        """Get recent digests."""
        return self._store.get_recent_digests(limit=limit)

    # -- Scoring feedback operations ----------------------------------------

    def record_scoring_feedback(
        self,
        opportunity_id: str,
        feedback_type: str,
        signal_id: str | None = None,
        scoring_features: dict[str, float] | None = None,
        rank_position: int | None = None,
        outcome: str | None = None,
    ) -> ScoringFeedback:
        """Record feedback on opportunity scoring for tuning.

        Args:
            opportunity_id: The opportunity that was scored.
            feedback_type: Type of feedback (useful, not_useful, etc.).
            signal_id: Signal that contributed to score (optional).
            scoring_features: Feature scores at ranking time.
            rank_position: Position in ranking when shown.
            outcome: Whether the operator acted on this.

        Returns:
            Created ScoringFeedback entry.
        """
        entry = ScoringFeedback(
            opportunity_id=opportunity_id,
            signal_id=signal_id,
            feedback_type=FeedbackType(feedback_type),
            scoring_features=scoring_features or {},
            rank_position=rank_position,
            outcome=outcome,
        )
        self._store.add_scoring_feedback(entry)
        return entry

    def get_scoring_feedback(self, opportunity_id: str) -> list[ScoringFeedback]:
        """Get all scoring feedback for an opportunity."""
        return self._store.get_scoring_feedback_for_opportunity(opportunity_id)

    def get_scoring_outcomes(self) -> dict[str, int]:
        """Get feedback outcome counts for tuning analysis."""
        return self._store.get_scoring_outcomes()

    # -- Bulk opportunity operations -----------------------------------------

    def bulk_update_status(
        self,
        opportunity_ids: list[str],
        status: str,
        reason: str | None = None,
    ) -> list[Opportunity]:
        """Update status for multiple opportunities.

        Args:
            opportunity_ids: List of opportunity IDs to update.
            status: New status.
            reason: Optional reason for the change.

        Returns:
            List of updated opportunities.
        """
        updated = []
        for opp_id in opportunity_ids:
            result = self.update_opportunity_status(opp_id, status, reason=reason)
            if result is not None:
                updated.append(result)
        return updated

    def get_opportunities_by_state(
        self,
        status: str,
        owner: str | None = None,
        priority: str | None = None,
    ) -> list[Opportunity]:
        """Get opportunities filtered by state and governance fields.

        Args:
            status: Opportunity status to filter by.
            owner: Optional owner filter.
            priority: Optional priority filter.

        Returns:
            List of matching opportunities.
        """
        from cc_deep_research.radar.models import OpportunityOwnerPriority

        opportunities = self.list_opportunities(status=status)
        if owner is not None:
            opportunities = [o for o in opportunities if o.owner == owner]
        if priority is not None:
            opportunities = [o for o in opportunities if o.priority == OpportunityOwnerPriority(priority)]
        return opportunities
