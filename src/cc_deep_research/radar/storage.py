"""Transactional persistence for Radar entities.

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

Legacy YAML files are imported on first access. SQLite then becomes the
authoritative store so writes are atomic and safe across concurrent processes.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.config import get_default_config_path
from cc_deep_research.radar._path_utils import is_safe_path
from cc_deep_research.radar.models import (
    AlertMute,
    AlertMuteList,
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
    RadarAlert,
    RadarAlertList,
    RadarDigest,
    RadarDigestList,
    RadarSource,
    RadarSourceList,
    RawSignal,
    RawSignalList,
    ScanJob,
    ScanJobList,
    ScoringFeedback,
    ScoringFeedbackList,
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
    "scan_jobs": "radar_scan_jobs.yaml",
    "alerts": "radar_alerts.yaml",
    "digests": "radar_digests.yaml",
    "alert_mutes": "radar_alert_mutes.yaml",
    "scoring_feedback": "radar_scoring_feedback.yaml",
}


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
        if not is_safe_path(explicit_path):
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
    """Load and save Radar entities through a transactional SQLite store.

    This store provides CRUD operations for all Radar entity types using
    separate YAML files per entity kind. This allows independent access
    patterns (e.g., updating scores without rewriting signals).

    All files live under ``~/.config/inqulume-studio/radar/`` by default.
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
            if not is_safe_path(radar_dir):
                raise ValueError(f"radar_dir {radar_dir} escapes allowed directories")
            self._radar_dir = radar_dir
        else:
            self._radar_dir = _default_radar_dir()

        self._radar_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._radar_dir / "radar.db"
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    @property
    def radar_dir(self) -> Path:
        """Return the radar directory path."""
        return self._radar_dir

    @property
    def db_path(self) -> Path:
        """Return the canonical Radar SQLite database path."""
        return self._db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Return the shared WAL connection; callers must hold ``_lock``."""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        if not self._initialized:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS radar_collections (
                    kind TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.commit()
            self._initialized = True
        return self._conn

    def _load_payload(self, kind: str, legacy_path: Path) -> dict[str, Any]:
        """Load one collection, importing its legacy YAML file once."""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT payload FROM radar_collections WHERE kind = ?",
                (kind,),
            ).fetchone()
            if row is not None:
                return dict(json.loads(row[0]))

            if not legacy_path.exists():
                return {}
            data = yaml.safe_load(legacy_path.read_text()) or {}
            if not isinstance(data, dict):
                raise ValueError(f"Invalid Radar {kind} payload: expected mapping")
            conn.execute(
                "INSERT INTO radar_collections (kind, payload, updated_at) VALUES (?, ?, ?)",
                (kind, json.dumps(data, separators=(",", ":")), _now_iso()),
            )
            conn.commit()
            return data

    def _save_payload(self, kind: str, data: dict[str, Any]) -> None:
        """Atomically replace one collection in the canonical database."""
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                INSERT INTO radar_collections (kind, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(kind) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                WHERE radar_collections.payload <> excluded.payload
                """,
                (kind, payload, _now_iso()),
            )
            conn.commit()

    # -- Source operations ----------------------------------------------------

    def _sources_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["sources"]

    def load_sources(self) -> RadarSourceList:
        """Load all radar sources from disk."""
        path = self._sources_path()
        data = self._load_payload("sources", path)
        return RadarSourceList.model_validate(data)

    def save_sources(self, sources: list[RadarSource]) -> None:
        """Persist all radar sources to disk."""
        container = RadarSourceList(sources=sources, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("sources", data)

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
                updated_data["updated_at"] = _now_iso()
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
        data = self._load_payload("signals", path)
        return RawSignalList.model_validate(data)

    def save_signals(self, signals: list[RawSignal]) -> None:
        """Persist all raw signals to disk."""
        container = RawSignalList(signals=signals, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("signals", data)

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
        data = self._load_payload("opportunities", path)
        return OpportunityList.model_validate(data)

    def save_opportunities(self, opportunities: list[Opportunity]) -> None:
        """Persist all opportunities to disk."""
        container = OpportunityList(opportunities=opportunities, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("opportunities", data)

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
                updated_data["updated_at"] = _now_iso()
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
        data = self._load_payload("scores", path)
        return OpportunityScoreList.model_validate(data)

    def save_scores(self, scores: list[OpportunityScore]) -> None:
        """Persist all opportunity scores to disk."""
        container = OpportunityScoreList(scores=scores, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("scores", data)

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
        data = self._load_payload("signal_links", path)
        return OpportunitySignalLinkList.model_validate(data)

    def save_signal_links(self, links: list[OpportunitySignalLink]) -> None:
        """Persist all signal links to disk."""
        container = OpportunitySignalLinkList(links=links, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("signal_links", data)

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
        data = self._load_payload("feedback", path)
        return OpportunityFeedbackList.model_validate(data)

    def save_feedback(self, entries: list[OpportunityFeedback]) -> None:
        """Persist all feedback entries to disk."""
        container = OpportunityFeedbackList(feedback_entries=entries, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("feedback", data)

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
        counts: dict[FeedbackType, int] = dict.fromkeys(FeedbackType, 0)
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
        data = self._load_payload("workflow_links", path)
        return WorkflowLinkList.model_validate(data)

    def save_workflow_links(self, links: list[WorkflowLink]) -> None:
        """Persist all workflow links to disk."""
        container = WorkflowLinkList(links=links, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("workflow_links", data)

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
        data = self._load_payload("status_history", path)
        return StatusHistoryList.model_validate(data)

    def save_status_history(self, entries: list[StatusHistoryEntry]) -> None:
        """Persist all status history entries to disk."""
        container = StatusHistoryList(entries=entries, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("status_history", data)

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

    # -- Scan job operations ---------------------------------------------------

    def _scan_jobs_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["scan_jobs"]

    def load_scan_jobs(self) -> ScanJobList:
        """Load all scan job records from disk."""
        path = self._scan_jobs_path()
        data = self._load_payload("scan_jobs", path)
        return ScanJobList.model_validate(data)

    def save_scan_jobs(self, jobs: list[ScanJob]) -> None:
        """Persist all scan job records to disk."""
        container = ScanJobList(jobs=jobs, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("scan_jobs", data)

    def add_scan_job(self, job: ScanJob) -> None:
        """Add a scan job record and persist."""
        jobs = self.load_scan_jobs()
        jobs.jobs.append(job)
        self.save_scan_jobs(jobs.jobs)

    def update_scan_job(self, job_id: str, patch: dict[str, Any]) -> ScanJob | None:
        """Update a scan job record by id. Returns updated job or None."""
        jobs = self.load_scan_jobs()
        for i, job in enumerate(jobs.jobs):
            if job.id == job_id:
                updated_data = job.model_dump(mode="python")
                updated_data.update(patch)
                if "status" in patch and isinstance(patch["status"], str):
                    from cc_deep_research.radar.models import ScanJobStatus
                    updated_data["status"] = ScanJobStatus(patch["status"])
                if "completed_at" not in updated_data and patch.get("status") in ("completed", "failed", "cancelled", "skipped"):
                    updated_data["completed_at"] = _now_iso()
                updated = ScanJob.model_validate(updated_data)
                jobs.jobs[i] = updated
                self.save_scan_jobs(jobs.jobs)
                return updated
        return None

    def get_scan_jobs_for_source(self, source_id: str, limit: int | None = None) -> list[ScanJob]:
        """Get scan jobs for a specific source, most recent first."""
        jobs = self.load_scan_jobs().jobs
        filtered = [j for j in jobs if j.source_id == source_id]
        filtered.sort(key=lambda j: j.started_at, reverse=True)
        if limit is not None:
            filtered = filtered[:limit]
        return filtered

    def get_recent_scan_jobs(self, limit: int = 50) -> list[ScanJob]:
        """Get the most recent scan jobs across all sources."""
        jobs = self.load_scan_jobs().jobs
        jobs.sort(key=lambda j: j.started_at, reverse=True)
        return jobs[:limit]

    def get_pending_scan_job(self, source_id: str) -> ScanJob | None:
        """Check if there's a pending/running scan for this source."""
        jobs = self.load_scan_jobs().jobs
        for job in jobs:
            if job.source_id == source_id and job.status in ("pending", "running"):
                return job
        return None

    # -- Alert operations ------------------------------------------------------

    def _alerts_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["alerts"]

    def load_alerts(self) -> RadarAlertList:
        """Load all radar alerts from disk."""
        path = self._alerts_path()
        data = self._load_payload("alerts", path)
        return RadarAlertList.model_validate(data)

    def save_alerts(self, alerts: list[RadarAlert]) -> None:
        """Persist all radar alerts to disk."""
        container = RadarAlertList(alerts=alerts, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("alerts", data)

    def add_alert(self, alert: RadarAlert) -> None:
        """Add an alert and persist."""
        alerts = self.load_alerts()
        alerts.alerts.append(alert)
        self.save_alerts(alerts.alerts)

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> RadarAlert | None:
        """Acknowledge an alert."""
        alerts = self.load_alerts()
        for i, alert in enumerate(alerts.alerts):
            if alert.id == alert_id:
                alerts.alerts[i].acknowledged = True
                alerts.alerts[i].acknowledged_by = acknowledged_by
                alerts.alerts[i].acknowledged_at = _now_iso()
                self.save_alerts(alerts.alerts)
                return alerts.alerts[i]
        return None

    def get_unacknowledged_alerts(self) -> list[RadarAlert]:
        """Get all unacknowledged alerts."""
        alerts = self.load_alerts()
        return [a for a in alerts.alerts if not a.acknowledged]

    def get_alerts_by_trigger(self, trigger: str) -> list[RadarAlert]:
        """Get all alerts for a specific trigger."""
        alerts = self.load_alerts()
        return [a for a in alerts.alerts if a.trigger.value == trigger]

    def clear_resolved_alerts(self, older_than_days: int = 30) -> int:
        """Clear acknowledged alerts older than specified days. Returns count cleared."""
        cutoff = (datetime.now(tz=UTC) - timedelta(days=older_than_days)).isoformat()
        alerts = self.load_alerts()
        original = len(alerts.alerts)
        alerts.alerts = [
            a for a in alerts.alerts
            if not a.acknowledged or a.created_at >= cutoff
        ]
        self.save_alerts(alerts.alerts)
        return original - len(alerts.alerts)

    # -- Digest operations ----------------------------------------------------

    def _digests_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["digests"]

    def load_digests(self) -> RadarDigestList:
        """Load all radar digests from disk."""
        path = self._digests_path()
        data = self._load_payload("digests", path)
        return RadarDigestList.model_validate(data)

    def save_digests(self, digests: list[RadarDigest]) -> None:
        """Persist all radar digests to disk."""
        container = RadarDigestList(digests=digests, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("digests", data)

    def add_digest(self, digest: RadarDigest) -> None:
        """Add a digest and persist."""
        digests = self.load_digests()
        digests.digests.append(digest)
        self.save_digests(digests.digests)

    def get_recent_digests(self, limit: int = 12) -> list[RadarDigest]:
        """Get the most recent digests."""
        digests = self.load_digests().digests
        digests.sort(key=lambda d: d.created_at, reverse=True)
        return digests[:limit]

    # -- Alert mute operations -------------------------------------------------

    def _alert_mutes_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["alert_mutes"]

    def load_alert_mutes(self) -> AlertMuteList:
        """Load all alert mutes from disk."""
        path = self._alert_mutes_path()
        data = self._load_payload("alert_mutes", path)
        return AlertMuteList.model_validate(data)

    def save_alert_mutes(self, mutes: list[AlertMute]) -> None:
        """Persist all alert mutes to disk."""
        container = AlertMuteList(mutes=mutes, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("alert_mutes", data)

    def add_alert_mute(self, mute: AlertMute) -> None:
        """Add an alert mute and persist."""
        mutes = self.load_alert_mutes()
        mutes.mutes.append(mute)
        self.save_alert_mutes(mutes.mutes)

    def remove_alert_mute(self, mute_id: str) -> bool:
        """Remove an alert mute. Returns True if removed."""
        mutes = self.load_alert_mutes()
        original = len(mutes.mutes)
        mutes.mutes = [m for m in mutes.mutes if m.id != mute_id]
        if len(mutes.mutes) < original:
            self.save_alert_mutes(mutes.mutes)
            return True
        return False

    def is_alert_muted(self, trigger: str, source_id: str | None = None) -> bool:
        """Check if an alert trigger is muted for a source or globally."""
        mutes = self.load_alert_mutes()
        now = datetime.now(tz=UTC).isoformat()
        for mute in mutes.mutes:
            if mute.trigger.value != trigger:
                continue
            # Check expiration
            if mute.expires_at is not None and mute.expires_at < now:
                continue
            # Check source match or global
            if mute.source_id is None or mute.source_id == source_id:
                return True
        return False

    # -- Scoring feedback operations ------------------------------------------

    def _scoring_feedback_path(self) -> Path:
        return self._radar_dir / FILE_NAMES["scoring_feedback"]

    def load_scoring_feedback(self) -> ScoringFeedbackList:
        """Load all scoring feedback from disk."""
        path = self._scoring_feedback_path()
        data = self._load_payload("scoring_feedback", path)
        return ScoringFeedbackList.model_validate(data)

    def save_scoring_feedback(self, entries: list[ScoringFeedback]) -> None:
        """Persist all scoring feedback to disk."""
        container = ScoringFeedbackList(feedback_entries=entries, last_updated=_now_iso())
        data = _serialize_model_to_dict(container)
        self._save_payload("scoring_feedback", data)

    def add_scoring_feedback(self, entry: ScoringFeedback) -> None:
        """Add a scoring feedback entry and persist."""
        feedback = self.load_scoring_feedback()
        feedback.feedback_entries.append(entry)
        self.save_scoring_feedback(feedback.feedback_entries)

    def get_scoring_feedback_for_opportunity(self, opportunity_id: str) -> list[ScoringFeedback]:
        """Get all scoring feedback for an opportunity."""
        feedback = self.load_scoring_feedback()
        return [f for f in feedback.feedback_entries if f.opportunity_id == opportunity_id]

    def get_recent_scoring_feedback(self, limit: int = 100) -> list[ScoringFeedback]:
        """Get recent scoring feedback for analysis."""
        feedback = self.load_scoring_feedback().feedback_entries
        feedback.sort(key=lambda f: f.created_at, reverse=True)
        return feedback[:limit]

    def get_scoring_outcomes(self, feedback_types: list[str] | None = None) -> dict[str, int]:
        """Get counts of feedback outcomes for tuning.

        Args:
            feedback_types: Only count these feedback types (default: useful/not_useful).

        Returns:
            Dict mapping feedback type to count.
        """
        if feedback_types is None:
            feedback_types = ["useful", "not_useful", "duplicate", "stale", "too_broad", "wrong_audience"]
        feedback = self.load_scoring_feedback().feedback_entries
        counts: dict[str, int] = {}
        for entry in feedback:
            ft = entry.feedback_type.value
            if ft in feedback_types:
                counts[ft] = counts.get(ft, 0) + 1
        return counts
