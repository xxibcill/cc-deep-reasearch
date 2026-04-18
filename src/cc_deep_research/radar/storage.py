"""YAML persistence for Radar entities.

Radar stores all entities as YAML files in the radar subdirectory of the
app config directory. Each entity type has its own file for independent
access patterns:

- radar_sources.yaml    - RadarSource records
- radar_signals.yaml    - RawSignal records
- radar_opportunities.yaml - Opportunity records
- radar_scores.yaml     - OpportunityScore records
- radar_signal_links.yaml - OpportunitySignalLink records
- radar_feedback.yaml  - OpportunityFeedback records
- radar_workflow_links.yaml - WorkflowLink records

This follows the existing content-gen storage pattern of one file per entity type.
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.config import get_default_config_path
from cc_deep_research.radar.models import (
    FeedbackType,
    FreshnessState,
    Opportunity,
    OpportunityFeedback,
    OpportunityFeedbackList,
    OpportunityList,
    OpportunityScore,
    OpportunityScoreList,
    OpportunitySignalLink,
    OpportunitySignalLinkList,
    OpportunityStatus,
    OpportunityType,
    RadarSource,
    RadarSourceList,
    RawSignal,
    RawSignalList,
    StatusHistoryEntry,
    StatusHistoryList,
    WorkflowLink,
    WorkflowLinkList,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

RADAR_SUBDIR_NAME = "radar"
FILE_NAMES = {
    "sources": "radar_sources.yaml",
    "signals": "radar_signals.yaml",
    "opportunities": "radar_opportunities.yaml",
    "scores": "radar_scores.yaml",
    "signal_links": "radar_signal_links.yaml",
    "feedback": "radar_feedback.yaml",
    "workflow_links": "radar_workflow_links.yaml",
    "status_history": "radar_status_history.yaml",
}


def _allowed_prefixes() -> tuple[str, ...]:
    """Compute allowed path prefixes at runtime."""
    return (
        str(Path.home() / ".config"),
        "/tmp",
        os.path.realpath(tempfile.gettempdir()),
        str(Path.cwd().resolve()),
    )


def _is_safe_path(path: Path) -> bool:
    """Reject paths that escape intended storage directories."""
    try:
        resolved = path.resolve()
        for prefix in _allowed_prefixes():
            resolved_prefix = Path(prefix).resolve()
            if str(resolved).startswith(str(resolved_prefix)):
                return True
        if not path.is_absolute():
            return True
        return False
    except (OSError, ValueError):
        return False


def _default_radar_dir() -> Path:
    """Return the default radar directory."""
    return get_default_config_path().parent / RADAR_SUBDIR_NAME


def resolve_radar_file_path(
    file_key: str,
    explicit_path: Path | None = None,
) -> Path:
    """Resolve a radar file path from explicit path or defaults.

    Args:
        file_key: One of 'sources', 'signals', 'opportunities', 'scores',
                  'signal_links', 'feedback', 'workflow_links'.
        explicit_path: Optional explicit path override.
    """
    if explicit_path is not None:
        if not _is_safe_path(explicit_path):
            raise ValueError(f"Explicit path {explicit_path} escapes allowed directories")
        return explicit_path

    filename = FILE_NAMES.get(file_key)
    if filename is None:
        raise ValueError(f"Unknown radar file key: {file_key}")

    return _default_radar_dir() / filename


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_model_to_dict(model: Any) -> dict[str, Any]:
    """Serialize a Pydantic model to a plain dict, converting enums to string values."""
    from enum import Enum

    def _convert_value(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {k: _convert_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_convert_value(item) for item in value]
        return value

    data = model.model_dump(exclude_none=True)
    return _convert_value(data)


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(tz=UTC).isoformat()


# ---------------------------------------------------------------------------
# RadarStore
# ---------------------------------------------------------------------------


class RadarStore:
    """Load and save Radar entities to YAML files.

    This store provides CRUD operations for all Radar entity types using
    separate YAML files per entity kind. This allows independent access
    patterns (e.g., updating scores without rewriting signals).

    All files live under ``~/.config/cc-deep-research/radar/`` by default.
    """

    def __init__(
        self,
        radar_dir: Path | None = None,
        *,
        config: Config | None = None,
    ) -> None:
        """Initialize the Radar store.

        Args:
            radar_dir: Optional explicit directory for all radar files.
            config: Optional config instance (unused, for API consistency).
        """
        if radar_dir is not None:
            if not _is_safe_path(radar_dir):
                raise ValueError(f"radar_dir {radar_dir} escapes allowed directories")
            self._radar_dir = radar_dir
        else:
            self._radar_dir = _default_radar_dir()

        self._radar_dir.mkdir(parents=True, exist_ok=True)

    @property
    def radar_dir(self) -> Path:
        """Return the radar directory path."""
        return self._radar_dir

    # -- Source operations ----------------------------------------------------

    def _sources_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["sources"]

    def load_sources(self) -> RadarSourceList:
        """Load all radar sources from disk."""
        path = self._sources_path()
        if not path.exists():
            return RadarSourceList()
        data = yaml.safe_load(path.read_text()) or {}
        return RadarSourceList.model_validate(data)

    def save_sources(self, sources: list[RadarSource]) -> None:
        """Persist all radar sources to disk."""
        path = self._sources_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        container = RadarSourceList(sources=sources, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_source(self, source: RadarSource) -> None:
        """Add a single source and persist."""
        sources = self.load_sources()
        sources.sources.append(source)
        self.save_sources(sources.sources)

    def get_source(self, source_id: str) -> RadarSource | None:
        """Get a source by id."""
        sources = self.load_sources()
        for src in sources.sources:
            if src.id == source_id:
                return src
        return None

    def update_source(self, source_id: str, patch: dict[str, Any]) -> RadarSource | None:
        """Update a source by id and persist. Returns updated source or None."""
        sources = self.load_sources()
        for i, src in enumerate(sources.sources):
            if src.id == source_id:
                updated_data = src.model_dump(mode="python")
                unsupported = sorted(set(patch) - set(updated_data.keys()))
                if unsupported:
                    raise ValueError(f"Unsupported source fields: {', '.join(unsupported)}")
                updated_data.update(patch)
                updated = RadarSource.model_validate(updated_data)
                sources.sources[i] = updated
                self.save_sources(sources.sources)
                return updated
        return None

    def delete_source(self, source_id: str) -> bool:
        """Delete a source by id. Returns True if deleted."""
        sources = self.load_sources()
        original = len(sources.sources)
        sources.sources = [s for s in sources.sources if s.id != source_id]
        if len(sources.sources) < original:
            self.save_sources(sources.sources)
            return True
        return False

    # -- Signal operations -----------------------------------------------------

    def _signals_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["signals"]

    def load_signals(self) -> RawSignalList:
        """Load all raw signals from disk."""
        path = self._signals_path()
        if not path.exists():
            return RawSignalList()
        data = yaml.safe_load(path.read_text()) or {}
        return RawSignalList.model_validate(data)

    def save_signals(self, signals: list[RawSignal]) -> None:
        """Persist all raw signals to disk."""
        path = self._signals_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        container = RawSignalList(signals=signals, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_signal(self, signal: RawSignal) -> None:
        """Add a single raw signal and persist."""
        signals = self.load_signals()
        signals.signals.append(signal)
        self.save_signals(signals.signals)

    def add_signals(self, new_signals: list[RawSignal]) -> None:
        """Add multiple raw signals and persist."""
        signals = self.load_signals()
        signals.signals.extend(new_signals)
        self.save_signals(signals.signals)

    def get_signal(self, signal_id: str) -> RawSignal | None:
        """Get a raw signal by id."""
        signals = self.load_signals()
        for sig in signals.signals:
            if sig.id == signal_id:
                return sig
        return None

    # -- Opportunity operations ------------------------------------------------

    def _opportunities_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["opportunities"]

    def load_opportunities(self) -> OpportunityList:
        """Load all opportunities from disk."""
        path = self._opportunities_path()
        if not path.exists():
            return OpportunityList()
        data = yaml.safe_load(path.read_text()) or {}
        return OpportunityList.model_validate(data)

    def save_opportunities(self, opportunities: list[Opportunity]) -> None:
        """Persist all opportunities to disk."""
        path = self._opportunities_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        container = OpportunityList(opportunities=opportunities, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_opportunity(self, opportunity: Opportunity) -> None:
        """Add a single opportunity and persist."""
        opportunities = self.load_opportunities()
        opportunities.opportunities.append(opportunity)
        self.save_opportunities(opportunities.opportunities)

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        """Get an opportunity by id."""
        opportunities = self.load_opportunities()
        for opp in opportunities.opportunities:
            if opp.id == opportunity_id:
                return opp
        return None

    def update_opportunity(
        self,
        opportunity_id: str,
        patch: dict[str, Any],
    ) -> Opportunity | None:
        """Update an opportunity by id and persist. Returns updated or None."""
        opportunities = self.load_opportunities()
        for i, opp in enumerate(opportunities.opportunities):
            if opp.id == opportunity_id:
                updated_data = opp.model_dump(mode="python")
                unsupported = sorted(set(patch) - set(updated_data.keys()))
                if unsupported:
                    raise ValueError(
                        f"Unsupported opportunity fields: {', '.join(unsupported)}"
                    )
                updated_data.update(patch)
                updated = Opportunity.model_validate(updated_data)
                opportunities.opportunities[i] = updated
                self.save_opportunities(opportunities.opportunities)
                return updated
        return None

    def delete_opportunity(self, opportunity_id: str) -> bool:
        """Delete an opportunity by id. Returns True if deleted."""
        opportunities = self.load_opportunities()
        original = len(opportunities.opportunities)
        opportunities.opportunities = [
            o for o in opportunities.opportunities if o.id != opportunity_id
        ]
        if len(opportunities.opportunities) < original:
            self.save_opportunities(opportunities.opportunities)
            return True
        return False

    def list_opportunities(
        self,
        status: OpportunityStatus | None = None,
        opportunity_type: OpportunityType | None = None,
        freshness: FreshnessState | None = None,
        limit: int | None = None,
    ) -> list[Opportunity]:
        """List opportunities with optional filtering.

        Args:
            status: Filter by opportunity status.
            opportunity_type: Filter by opportunity type.
            freshness: Filter by freshness state.
            limit: Maximum number to return.

        Returns:
            Filtered list of opportunities sorted by created_at desc.
        """
        opportunities = self.load_opportunities().opportunities

        if status is not None:
            opportunities = [o for o in opportunities if o.status == status]
        if opportunity_type is not None:
            opportunities = [o for o in opportunities if o.opportunity_type == opportunity_type]
        if freshness is not None:
            opportunities = [o for o in opportunities if o.freshness_state == freshness]

        # Sort by total_score desc, then by last_detected_at desc
        opportunities.sort(key=lambda o: (-o.total_score, o.last_detected_at))

        if limit is not None:
            opportunities = opportunities[:limit]

        return opportunities

    # -- Score operations -----------------------------------------------------

    def _scores_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["scores"]

    def load_scores(self) -> OpportunityScoreList:
        """Load all opportunity scores from disk."""
        path = self._scores_path()
        if not path.exists():
            return OpportunityScoreList()
        data = yaml.safe_load(path.read_text()) or {}
        return OpportunityScoreList.model_validate(data)

    def save_scores(self, scores: list[OpportunityScore]) -> None:
        """Persist all opportunity scores to disk."""
        path = self._scores_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        container = OpportunityScoreList(scores=scores, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def upsert_score(self, score: OpportunityScore) -> None:
        """Add or replace a score for an opportunity."""
        scores = self.load_scores()
        for i, s in enumerate(scores.scores):
            if s.opportunity_id == score.opportunity_id:
                scores.scores[i] = score
                self.save_scores(scores.scores)
                return
        scores.scores.append(score)
        self.save_scores(scores.scores)

    def get_score(self, opportunity_id: str) -> OpportunityScore | None:
        """Get the score for an opportunity."""
        scores = self.load_scores()
        for s in scores.scores:
            if s.opportunity_id == opportunity_id:
                return s
        return None

    # -- Signal link operations -----------------------------------------------

    def _signal_links_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["signal_links"]

    def load_signal_links(self) -> OpportunitySignalLinkList:
        """Load all opportunity-signal links from disk."""
        path = self._signal_links_path()
        if not path.exists():
            return OpportunitySignalLinkList()
        data = yaml.safe_load(path.read_text()) or {}
        return OpportunitySignalLinkList.model_validate(data)

    def save_signal_links(self, links: list[OpportunitySignalLink]) -> None:
        """Persist all signal links to disk."""
        path = self._signal_links_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        container = OpportunitySignalLinkList(links=links, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def link_signal_to_opportunity(
        self,
        opportunity_id: str,
        raw_signal_id: str,
        link_reason: str | None = None,
    ) -> None:
        """Link a raw signal to an opportunity."""
        links = self.load_signal_links()
        # Check for duplicate
        for link in links.links:
            if link.opportunity_id == opportunity_id and link.raw_signal_id == raw_signal_id:
                return
        links.links.append(
            OpportunitySignalLink(
                opportunity_id=opportunity_id,
                raw_signal_id=raw_signal_id,
                link_reason=link_reason,
            )
        )
        self.save_signal_links(links.links)

    def get_signal_ids_for_opportunity(self, opportunity_id: str) -> list[str]:
        """Get all signal ids linked to an opportunity."""
        links = self.load_signal_links()
        return [link.raw_signal_id for link in links.links if link.opportunity_id == opportunity_id]

    def get_opportunity_ids_for_signal(self, raw_signal_id: str) -> list[str]:
        """Get all opportunity ids linked to a signal."""
        links = self.load_signal_links()
        return [
            link.opportunity_id for link in links.links if link.raw_signal_id == raw_signal_id
        ]

    # -- Feedback operations -------------------------------------------------

    def _feedback_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["feedback"]

    def load_feedback(self) -> OpportunityFeedbackList:
        """Load all feedback entries from disk."""
        path = self._feedback_path()
        if not path.exists():
            return OpportunityFeedbackList()
        data = yaml.safe_load(path.read_text()) or {}
        return OpportunityFeedbackList.model_validate(data)

    def save_feedback(self, entries: list[OpportunityFeedback]) -> None:
        """Persist all feedback entries to disk."""
        path = self._feedback_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        container = OpportunityFeedbackList(feedback_entries=entries, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_feedback(self, feedback: OpportunityFeedback) -> None:
        """Append a feedback entry and persist."""
        entries = self.load_feedback()
        entries.feedback_entries.append(feedback)
        self.save_feedback(entries.feedback_entries)

    def get_feedback_for_opportunity(self, opportunity_id: str) -> list[OpportunityFeedback]:
        """Get all feedback entries for an opportunity."""
        entries = self.load_feedback()
        return [e for e in entries.feedback_entries if e.opportunity_id == opportunity_id]

    def get_feedback_counts(
        self,
        opportunity_type: str | None = None,
        days_back: int = 30,
    ) -> dict[FeedbackType, int]:
        """Aggregate feedback counts, optionally filtered by opportunity type.

        Args:
            opportunity_type: If set, only count feedback for this opportunity type
                (stored in feedback metadata as 'opportunity_type').
            days_back: Only count feedback from the last N days.

        Returns:
            Dict mapping FeedbackType to count.
        """
        cutoff = (datetime.now(tz=UTC) - timedelta(days=days_back)).isoformat()
        counts: dict[FeedbackType, int] = {ft: 0 for ft in FeedbackType}
        for fb in self.load_feedback().feedback_entries:
            if fb.created_at < cutoff:
                continue
            if opportunity_type is not None:
                if fb.metadata.get("opportunity_type") != opportunity_type:
                    continue
            counts[fb.feedback_type] += 1
        return counts

    # -- Workflow link operations ---------------------------------------------

    def _workflow_links_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["workflow_links"]

    def load_workflow_links(self) -> WorkflowLinkList:
        """Load all workflow links from disk."""
        path = self._workflow_links_path()
        if not path.exists():
            return WorkflowLinkList()
        data = yaml.safe_load(path.read_text()) or {}
        return WorkflowLinkList.model_validate(data)

    def save_workflow_links(self, links: list[WorkflowLink]) -> None:
        """Persist all workflow links to disk."""
        path = self._workflow_links_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        container = WorkflowLinkList(links=links, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_workflow_link(self, link: WorkflowLink) -> None:
        """Add a workflow link and persist."""
        links = self.load_workflow_links()
        links.links.append(link)
        self.save_workflow_links(links.links)

    def get_workflow_links_for_opportunity(
        self,
        opportunity_id: str,
    ) -> list[WorkflowLink]:
        """Get all workflow links for an opportunity."""
        links = self.load_workflow_links()
        return [link for link in links.links if link.opportunity_id == opportunity_id]

    # -- Status history operations -------------------------------------------

    def _status_history_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["status_history"]

    def load_status_history(self) -> StatusHistoryList:
        """Load all status history entries from disk."""
        path = self._status_history_path()
        if not path.exists():
            return StatusHistoryList()
        data = yaml.safe_load(path.read_text()) or {}
        return StatusHistoryList.model_validate(data)

    def save_status_history(self, entries: list[StatusHistoryEntry]) -> None:
        """Persist all status history entries to disk."""
        path = self._status_history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        container = StatusHistoryList(entries=entries, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_status_history_entry(self, entry: StatusHistoryEntry) -> None:
        """Append a status history entry and persist."""
        history = self.load_status_history()
        history.entries.append(entry)
        self.save_status_history(history.entries)

    def get_status_history_for_opportunity(
        self,
        opportunity_id: str,
    ) -> list[StatusHistoryEntry]:
        """Get all status history entries for an opportunity."""
        history = self.load_status_history()
        return [e for e in history.entries if e.opportunity_id == opportunity_id]

