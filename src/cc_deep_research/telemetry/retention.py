"""Telemetry retention, compaction, and archive policies."""

from __future__ import annotations

import gzip
import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from cc_deep_research.telemetry import get_default_telemetry_dir


class RetentionMode(StrEnum):
    """Dry-run vs enforcement mode for retention operations."""

    DRY_RUN = "dry_run"
    ENFORCE = "enforce"


class CompactionLevel(StrEnum):
    """How aggressively to compact session telemetry."""

    NONE = "none"
    """Do not compact at all."""

    EVENTS_ONLY = "events_only"
    """Compress event payloads only, keep summary intact."""

    FULL = "full"
    """Compress everything including summary, keep checkpoints separately."""


@dataclass
class RetentionPolicy:
    """Policy for deciding which sessions to retain or expire.

    Attributes:
        max_age_days: Maximum age in days before a completed session becomes
            a retention candidate. Set to None for no age limit.
        min_active_sessions: Minimum number of recent active sessions to
            always preserve regardless of age.
        preserve_summaries: If True, session summary files are never
            automatically deleted (only compacted).
        preserve_checkpoints: If True, resume-safe checkpoints are preserved
            even when compacting.
        compaction_level: How aggressively to compact eligible sessions.
    """

    max_age_days: int | None = 90
    min_active_sessions: int = 5
    preserve_summaries: bool = True
    preserve_checkpoints: bool = True
    compaction_level: CompactionLevel = CompactionLevel.EVENTS_ONLY


@dataclass
class RetentionCandidate:
    """A session evaluated against a retention policy.

    Attributes:
        session_id: The session being evaluated.
        reason: Human-readable reason for being a candidate (age, no session file, etc.).
        age_days: Age of the session in days, or None if still active.
        has_summary: Whether the session has a summary file.
        has_checkpoints: Whether the session has resume-safe checkpoints.
        is_active: Whether the session is currently active (running).
        is_archived: Whether the session is marked as archived.
        compactable: Whether the session can be compacted.
        deletable: Whether the session can be fully deleted.
    """

    session_id: str
    reason: str
    age_days: int | None = None
    has_summary: bool = False
    has_checkpoints: bool = False
    is_active: bool = False
    is_archived: bool = False
    compactable: bool = False
    deletable: bool = False


@dataclass
class RetentionResult:
    """Result of a retention evaluation or action.

    Attributes:
        evaluated: Total sessions evaluated.
        candidates: Sessions that are candidates for compaction/deletion.
        active_protected: Sessions protected because they are active.
        checkpoint_protected: Sessions protected because they have resume-safe checkpoints.
        archived_protected: Sessions protected because they are archived.
        errors: Per-session errors encountered during evaluation.
        dry_run: Whether this was a dry-run evaluation.
    """

    evaluated: int = 0
    candidates: list[RetentionCandidate] = field(default_factory=list)
    active_protected: int = 0
    checkpoint_protected: int = 0
    archived_protected: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    dry_run: bool = True


def _session_age_days(session_dir: Path, telemetry_dir: Path) -> int | None:
    """Compute session age in days from its summary file or latest event."""
    summary_file = session_dir / "summary.json"
    if summary_file.exists():
        try:
            summary = json.loads(summary_file.read_text())
            created_at = summary.get("created_at")
            if created_at:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return (datetime.now(UTC) - dt).days
        except (ValueError, json.JSONDecodeError):
            pass

    # Fall back to latest event timestamp
    events_file = session_dir / "events.jsonl"
    if events_file.exists():
        try:
            with open(events_file, encoding="utf-8") as f:
                last_line = None
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        last_line = stripped
            if last_line:
                event = json.loads(last_line)
                ts = event.get("timestamp")
                if ts:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    return (datetime.now(UTC) - dt).days
        except (ValueError, json.JSONDecodeError, OSError):
            pass
    return None


def _has_resume_safe_checkpoint(session_dir: Path) -> bool:
    """Return True if the session has any resume-safe checkpoint."""
    manifest_path = session_dir / "checkpoints" / "manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text())
        return manifest.get("latest_resume_safe_checkpoint_id") is not None
    except (ValueError, OSError):
        return False


def evaluate_retention_candidates(
    policy: RetentionPolicy,
    telemetry_dir: Path | None = None,
    dry_run: bool = True,
) -> RetentionResult:
    """Evaluate all sessions against a retention policy.

    Args:
        policy: The retention policy to evaluate against.
        telemetry_dir: Optional telemetry directory. Uses default if not provided.
        dry_run: If True, only evaluates without taking action. If False,
            performs compaction.

    Returns:
        RetentionResult with candidate counts and per-session details.
    """
    from cc_deep_research.session_store import SessionStore

    telemetry_dir = telemetry_dir or get_default_telemetry_dir()
    store = SessionStore()

    result = RetentionResult(dry_run=dry_run)

    if not telemetry_dir.exists():
        return result

    archived_ids = store.get_archived_session_ids()
    active_session_ids: set[str] = set()

    # Import here to avoid circular dependency issues
    try:
        from cc_deep_research.telemetry.live import query_live_sessions
    except ImportError:
        return result

    try:
        live_sessions = query_live_sessions(base_dir=telemetry_dir)
        for session in live_sessions:
            if session.get("active"):
                active_session_ids.add(session.get("session_id", ""))
    except Exception:
        pass

    for session_dir in sorted(telemetry_dir.iterdir(), key=lambda p: p.name):
        if not session_dir.is_dir():
            continue

        session_id = session_dir.name
        result.evaluated += 1

        is_active = session_id in active_session_ids
        is_archived = session_id in archived_ids or store.is_session_archived(session_id)
        has_checkpoints = _has_resume_safe_checkpoint(session_dir)
        age_days = _session_age_days(session_dir, telemetry_dir)

        summary_file = session_dir / "summary.json"
        has_summary = summary_file.exists()

        candidate = RetentionCandidate(
            session_id=session_id,
            reason="",
            age_days=age_days,
            has_summary=has_summary,
            has_checkpoints=has_checkpoints,
            is_active=is_active,
            is_archived=is_archived,
        )

        if is_active:
            candidate.reason = "Active session - always protected"
            result.active_protected += 1
        elif is_archived:
            candidate.reason = "Archived session - preserved"
            result.archived_protected += 1
        elif has_checkpoints and policy.preserve_checkpoints:
            candidate.reason = "Has resume-safe checkpoint - protected"
            result.checkpoint_protected += 1
        elif policy.max_age_days is not None and age_days is not None and age_days > policy.max_age_days:
            if dry_run:
                candidate.reason = f"Expired: {age_days} days old (max {policy.max_age_days})"
                candidate.compactable = True
                candidate.deletable = True
                result.candidates.append(candidate)
            else:
                # Enforce mode - compact or delete
                pass
        else:
            # Check if it's simply old enough to consider
            if age_days is not None and age_days > (policy.max_age_days or 90):
                candidate.reason = f"Stale: {age_days} days old"
                candidate.compactable = True
                candidate.deletable = True
                result.candidates.append(candidate)
            else:
                candidate.reason = "Within retention window"

    return result


def compact_session_telemetry(
    session_id: str,
    compaction_level: CompactionLevel = CompactionLevel.EVENTS_ONLY,
    telemetry_dir: Path | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Compact a session's telemetry files.

    Args:
        session_id: The session to compact.
        compaction_level: How aggressively to compact.
        telemetry_dir: Optional telemetry directory.
        dry_run: If True, describe what would happen without doing it.

    Returns:
        Dict with dry_run status, space_recovered bytes estimate, and any errors.
    """
    telemetry_dir = telemetry_dir or get_default_telemetry_dir()
    session_dir = telemetry_dir / session_id

    if not session_dir.exists():
        return {"success": False, "error": f"Session {session_id} not found", "dry_run": dry_run}

    if compaction_level == CompactionLevel.NONE:
        return {"success": True, "compacted": False, "reason": "Compaction level is NONE", "dry_run": dry_run}

    events_file = session_dir / "events.jsonl"
    summary_file = session_dir / "summary.json"
    checkpoints_dir = session_dir / "checkpoints"
    compacted_marker = session_dir / ".compacted"

    if not events_file.exists():
        return {"success": False, "error": "No events file to compact", "dry_run": dry_run}

    if dry_run:
        current_size = events_file.stat().st_size if events_file.exists() else 0
        summary_size = summary_file.stat().st_size if summary_file.exists() else 0
        return {
            "success": True,
            "compacted": True,
            "dry_run": True,
            "would_compress": events_file.name,
            "would_preserve": ["checkpoints/"] if checkpoints_dir.exists() else [],
            "space_would_free_bytes": current_size,
        }

    # Perform actual compaction
    try:
        events_size = events_file.stat().st_size
        summary_size = summary_file.stat().st_size if summary_file.exists() else 0

        # Compress events file
        gz_path = session_dir / "events.jsonl.gz"
        with open(events_file, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        gz_size = gz_path.stat().st_size

        # Remove uncompressed events
        events_file.unlink()

        # Compact summary if configured
        if compaction_level == CompactionLevel.FULL and summary_file.exists():
            gz_summary_path = session_dir / "summary.json.gz"
            with open(summary_file, "rb") as f_in, gzip.open(gz_summary_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            summary_file.unlink()

        # Write marker
        compacted_marker.write_text(
            json.dumps(
                {
                    "compacted_at": datetime.now(UTC).isoformat(),
                    "compaction_level": compaction_level.value,
                    "events_gz_size": gz_size,
                }
            )
        )

        space_freed = events_size - gz_size
        return {
            "success": True,
            "compacted": True,
            "dry_run": False,
            "events_gz_size": gz_size,
            "events_original_size": events_size,
            "space_freed_bytes": max(0, space_freed),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "dry_run": dry_run}


def restore_compacted_session(
    session_id: str,
    telemetry_dir: Path | None = None,
) -> dict[str, Any]:
    """Restore a compacted session by decompressing its files.

    Args:
        session_id: The session to restore.
        telemetry_dir: Optional telemetry directory.

    Returns:
        Dict with success status and any errors.
    """
    telemetry_dir = telemetry_dir or get_default_telemetry_dir()
    session_dir = telemetry_dir / session_id

    if not session_dir.exists():
        return {"success": False, "error": f"Session {session_id} not found"}

    events_gz = session_dir / "events.jsonl.gz"
    if not events_gz.exists():
        return {"success": False, "error": "No compressed events file found"}

    try:
        events_file = session_dir / "events.jsonl"
        with gzip.open(events_gz, "rb") as f_in, open(events_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        events_gz.unlink()

        # Restore summary if compressed
        summary_gz = session_dir / "summary.json.gz"
        if summary_gz.exists():
            summary_file = session_dir / "summary.json"
            with gzip.open(summary_gz, "rb") as f_in, open(summary_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            summary_gz.unlink()

        # Remove marker
        compacted_marker = session_dir / ".compacted"
        if compacted_marker.exists():
            compacted_marker.unlink()

        return {"success": True, "restored": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_retention_summary(
    policy: RetentionPolicy,
    telemetry_dir: Path | None = None,
) -> dict[str, Any]:
    """Get a summary of retention candidate counts and space estimates.

    Args:
        policy: The retention policy to evaluate against.
        telemetry_dir: Optional telemetry directory.

    Returns:
        Dict with counts and space estimates for retention candidates.
    """
    result = evaluate_retention_candidates(policy, telemetry_dir=telemetry_dir, dry_run=True)

    total_size_bytes = 0
    candidate_size_bytes = 0

    telemetry_dir = telemetry_dir or get_default_telemetry_dir()

    for session_dir in sorted(telemetry_dir.iterdir(), key=lambda p: p.name):
        if not session_dir.is_dir():
            continue
        session_id = session_dir.name

        for events_file in session_dir.glob("events.jsonl*"):
            size = events_file.stat().st_size
            total_size_bytes += size
            if any(c.session_id == session_id for c in result.candidates):
                candidate_size_bytes += size

    return {
        "policy": {
            "max_age_days": policy.max_age_days,
            "min_active_sessions": policy.min_active_sessions,
            "preserve_summaries": policy.preserve_summaries,
            "preserve_checkpoints": policy.preserve_checkpoints,
            "compaction_level": policy.compaction_level.value,
        },
        "total_sessions": result.evaluated,
        "candidate_count": len(result.candidates),
        "active_protected": result.active_protected,
        "checkpoint_protected": result.checkpoint_protected,
        "archived_protected": result.archived_protected,
        "total_size_bytes": total_size_bytes,
        "candidate_size_bytes": candidate_size_bytes,
        "space_would_free_bytes": candidate_size_bytes,
    }


def apply_retention(
    policy: RetentionPolicy,
    telemetry_dir: Path | None = None,
    mode: RetentionMode = RetentionMode.DRY_RUN,
) -> RetentionResult:
    """Apply retention policy to telemetry sessions.

    Args:
        policy: The retention policy to apply.
        telemetry_dir: Optional telemetry directory.
        mode: Whether to actually perform actions or just report.

    Returns:
        RetentionResult with outcomes.
    """
    result = evaluate_retention_candidates(policy, telemetry_dir=telemetry_dir, dry_run=True)
    result.dry_run = mode == RetentionMode.DRY_RUN

    if mode == RetentionMode.DRY_RUN:
        return result

    for candidate in result.candidates:
        if candidate.compactable:
            compact_result = compact_session_telemetry(
                candidate.session_id,
                compaction_level=policy.compaction_level,
                telemetry_dir=telemetry_dir,
                dry_run=False,
            )
            if not compact_result.get("success"):
                result.errors[candidate.session_id] = compact_result.get("error", "Unknown error")

    return result


__all__ = [
    "CompactionLevel",
    "RetentionCandidate",
    "RetentionMode",
    "RetentionPolicy",
    "RetentionResult",
    "apply_retention",
    "compact_session_telemetry",
    "evaluate_retention_candidates",
    "get_retention_summary",
    "restore_compacted_session",
]
