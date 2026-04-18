"""Service layer for Opportunity Radar.

RadarService wraps the RadarStore with business-logic operations that are
meaningful to routes and the opportunity engine. Service methods return typed
models and handle cross-entity operations (e.g., creating an opportunity
with its initial score, linking signals).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.radar.models import (
    FeedbackType,
    FreshnessState,
    Opportunity,
    OpportunityFeedback,
    OpportunityScore,
    OpportunityStatus,
    OpportunityType,
    RadarSource,
    RawSignal,
    WorkflowLink,
    WorkflowType,
)
from cc_deep_research.radar.storage import RadarStore

if TYPE_CHECKING:
    pass


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
        status: str | None = None,
    ) -> list[RadarSource]:
        """List all sources, optionally filtered by status.

        Args:
            status: Optional status to filter by (active, inactive, error).

        Returns:
            List of RadarSource records.
        """
        sources = self._store.load_sources().sources
        if status is not None:
            from cc_deep_research.radar.models import SourceStatus

            sources = [s for s in sources if s.status == SourceStatus(status)]
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
        status: str | None = None,
        opportunity_type: str | None = None,
        freshness: str | None = None,
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
        status_enum = OpportunityStatus(status) if status else None
        type_enum = OpportunityType(opportunity_type) if opportunity_type else None
        freshness_enum = FreshnessState(freshness) if freshness else None
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
    ) -> Opportunity | None:
        """Update the status of an opportunity.

        Args:
            opportunity_id: The opportunity to update.
            status: New status value.

        Returns:
            Updated Opportunity or None if not found.
        """
        return self._store.update_opportunity(
            opportunity_id,
            {"status": OpportunityStatus(status)},
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
