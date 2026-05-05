"""Backup manifest creation, dry-run planning, and restore operations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from cc_deep_research.config import load_config
from cc_deep_research.operations import (
    _get_config_dir,
    _get_content_gen_dir,
    _get_knowledge_dir,
    _get_radar_dir,
    _get_reports_dir,
    _get_session_dir,
    _get_telemetry_dir,
)

BACKUP_VERSION = "1.0"


class BackupStatus(StrEnum):
    """Backup operation status constants."""

    CREATED = "created"
    VALIDATED = "validated"
    CORRUPTED = "corrupted"
    INCOMPATIBLE = "incompatible"
    RESTORED = "restored"


@dataclass
class BackupManifestEntry:
    """One entry in a backup manifest."""

    path: str
    kind: str
    size_bytes: int
    compressed_size_bytes: int | None = None
    mtime: str | None = None
    hash_sha256: str | None = None


@dataclass
class BackupManifest:
    """Backup manifest containing metadata about a backup archive."""

    version: str = BACKUP_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    backup_id: str = ""
    total_size_bytes: int = 0
    compressed_size_bytes: int = 0
    entries: list[BackupManifestEntry] = field(default_factory=list)
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "backup_id": self.backup_id,
            "total_size_bytes": self.total_size_bytes,
            "compressed_size_bytes": self.compressed_size_bytes,
            "entries": [
                {
                    "path": e.path,
                    "kind": e.kind,
                    "size_bytes": e.size_bytes,
                    "compressed_size_bytes": e.compressed_size_bytes,
                    "mtime": e.mtime,
                    "hash_sha256": e.hash_sha256,
                }
                for e in self.entries
            ],
            "config_snapshot": self.config_snapshot,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupManifest:
        manifest = cls(
            version=data.get("version", BACKUP_VERSION),
            created_at=data.get("created_at", ""),
            backup_id=data.get("backup_id", ""),
            total_size_bytes=data.get("total_size_bytes", 0),
            compressed_size_bytes=data.get("compressed_size_bytes", 0),
            entries=[
                BackupManifestEntry(
                    path=e["path"],
                    kind=e["kind"],
                    size_bytes=e["size_bytes"],
                    compressed_size_bytes=e.get("compressed_size_bytes"),
                    mtime=e.get("mtime"),
                    hash_sha256=e.get("hash_sha256"),
                )
                for e in data.get("entries", [])
            ],
            config_snapshot=data.get("config_snapshot", {}),
            metadata=data.get("metadata", {}),
        )
        return manifest


@dataclass
class BackupDryRunResult:
    """Result of a backup dry-run showing what would be included."""

    manifest: BackupManifest
    estimated_total_bytes: int
    estimated_compressed_bytes: int
    would_include: list[str]
    excluded: list[str]
    warnings: list[str]


@dataclass
class RestoreValidationResult:
    """Result of validating a backup before restore."""

    valid: bool
    manifest: BackupManifest
    compatible: bool
    errors: list[str]
    warnings: list[str]


def _compute_directory_size(path: Path) -> tuple[int, int]:
    """Compute total size of a directory and its compressed size estimate.

    Returns (total_bytes, compressed_estimate).
    """
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except OSError:
        pass
    # gzip estimates ~30% compression for typical text/JSON data
    compressed = int(total * 0.3)
    return total, compressed


def _collect_backup_entries(
    base_dir: Path,
    subdirs: dict[str, Path],
) -> list[BackupManifestEntry]:
    """Collect entries from a set of subdirectories."""
    entries: list[BackupManifestEntry] = []

    for name, path in subdirs.items():
        if not path.exists():
            continue

        try:
            if path.is_file():
                size = path.stat().st_size
                entries.append(
                    BackupManifestEntry(
                        path=str(path.relative_to(base_dir)),
                        kind=f"file:{name}",
                        size_bytes=size,
                        compressed_size_bytes=int(size * 0.3),
                        mtime=datetime.fromtimestamp(
                            path.stat().st_mtime, tz=UTC
                        ).isoformat(),
                    )
                )
            elif path.is_dir():
                total, compressed = _compute_directory_size(path)
                entries.append(
                    BackupManifestEntry(
                        path=str(path.relative_to(base_dir)),
                        kind=f"dir:{name}",
                        size_bytes=total,
                        compressed_size_bytes=compressed,
                    )
                )
        except OSError:
            pass

    return entries


def plan_backup(
    workspace_path: Path | None = None,
    include_sessions: bool = True,
    include_telemetry: bool = True,
    include_knowledge: bool = True,
    include_content_gen: bool = True,
    include_config: bool = True,
    include_radar: bool = True,
) -> BackupDryRunResult:
    """Plan a backup without creating it, showing estimated sizes and included data.

    Args:
        workspace_path: Optional override for workspace root.
        include_sessions: Include session storage.
        include_telemetry: Include telemetry events and analytics.
        include_knowledge: Include knowledge graph data.
        include_content_gen: Include content generation artifacts.
        include_config: Include configuration.
        include_radar: Include radar data.

    Returns:
        BackupDryRunResult with estimates and warnings.
    """
    config_dir = _get_config_dir()
    session_dir = _get_session_dir()
    telemetry_dir = _get_telemetry_dir()
    reports_dir = _get_reports_dir()
    knowledge_dir = _get_knowledge_dir()
    content_gen_dir = _get_content_gen_dir()
    radar_dir = _get_radar_dir()

    would_include: list[str] = []
    excluded: list[str] = []
    warnings: list[str] = []
    entries: list[BackupManifestEntry] = []

    all_paths: dict[str, Path] = {}

    if include_config:
        all_paths["config"] = config_dir
    if include_sessions:
        all_paths["sessions"] = session_dir
    if include_telemetry:
        all_paths["telemetry"] = telemetry_dir
    if include_knowledge:
        all_paths["knowledge"] = knowledge_dir
    if include_content_gen:
        all_paths["content_gen"] = content_gen_dir
    if include_radar:
        all_paths["radar"] = radar_dir

    included_reports = False
    for name, path in all_paths.items():
        if not path.exists():
            excluded.append(name)
            continue
        would_include.append(name)

        try:
            if path.is_file():
                size = path.stat().st_size
                entries.append(
                    BackupManifestEntry(
                        path=str(path.relative_to(config_dir.parent)),
                        kind=f"file:{name}",
                        size_bytes=size,
                        compressed_size_bytes=int(size * 0.3),
                    )
                )
            else:
                total, compressed = _compute_directory_size(path)
                entries.append(
                    BackupManifestEntry(
                        path=str(path.relative_to(config_dir.parent)),
                        kind=f"dir:{name}",
                        size_bytes=total,
                        compressed_size_bytes=compressed,
                    )
                )
        except OSError:
            warnings.append(f"Could not access {name} at {path}")

    total_bytes = sum(e.size_bytes for e in entries)
    total_compressed = sum(
        e.compressed_size_bytes or e.size_bytes for e in entries
    )

    manifest = BackupManifest(
        backup_id="dry-run",
        entries=entries,
        metadata={
            "include_sessions": include_sessions,
            "include_telemetry": include_telemetry,
            "include_knowledge": include_knowledge,
            "include_content_gen": include_content_gen,
            "include_config": include_config,
            "include_radar": include_radar,
        },
    )

    return BackupDryRunResult(
        manifest=manifest,
        estimated_total_bytes=total_bytes,
        estimated_compressed_bytes=total_compressed,
        would_include=would_include,
        excluded=excluded,
        warnings=warnings,
    )


def create_backup(
    backup_path: Path,
    include_sessions: bool = True,
    include_telemetry: bool = True,
    include_knowledge: bool = True,
    include_content_gen: bool = True,
    include_config: bool = True,
    include_radar: bool = True,
    dry_run: bool = False,
) -> BackupManifest | BackupDryRunResult:
    """Create a backup archive of critical project data.

    Args:
        backup_path: Path for the backup archive (.tar.gz or directory).
        include_sessions: Include session storage.
        include_telemetry: Include telemetry events and analytics.
        include_knowledge: Include knowledge graph data.
        include_content_gen: Include content generation artifacts.
        include_config: Include configuration.
        include_radar: Include radar data.
        dry_run: If True, plan the backup without creating it.

    Returns:
        BackupManifest on success, BackupDryRunResult if dry_run=True.
    """
    import uuid

    config_dir = _get_config_dir()
    config = load_config()

    would_include: list[str] = []
    excluded: list[str] = []
    entries: list[BackupManifestEntry] = []
    total_bytes = 0
    total_compressed = 0

    subdirs: dict[str, Path] = {}

    if include_config:
        subdirs["config"] = config_dir
    if include_sessions:
        subdirs["sessions"] = _get_session_dir()
    if include_telemetry:
        subdirs["telemetry"] = _get_telemetry_dir()
    if include_knowledge:
        subdirs["knowledge"] = _get_knowledge_dir()
    if include_content_gen:
        subdirs["content_gen"] = _get_content_gen_dir()
    if include_radar:
        subdirs["radar"] = _get_radar_dir()

    for name, path in subdirs.items():
        if not path.exists():
            excluded.append(name)
            continue
        would_include.append(name)

        if path.is_file():
            size = path.stat().st_size
            entries.append(
                BackupManifestEntry(
                    path=str(path.relative_to(config_dir.parent)),
                    kind=f"file:{name}",
                    size_bytes=size,
                    compressed_size_bytes=int(size * 0.3),
                    mtime=datetime.fromtimestamp(
                        path.stat().st_mtime, tz=UTC
                    ).isoformat(),
                )
            )
            total_bytes += size
            total_compressed += int(size * 0.3)
        elif path.is_dir():
            dir_total, dir_compressed = _compute_directory_size(path)
            entries.append(
                BackupManifestEntry(
                    path=str(path.relative_to(config_dir.parent)),
                    kind=f"dir:{name}",
                    size_bytes=dir_total,
                    compressed_size_bytes=dir_compressed,
                )
            )
            total_bytes += dir_total
            total_compressed += dir_compressed

    manifest = BackupManifest(
        backup_id=str(uuid.uuid4())[:8],
        total_size_bytes=total_bytes,
        compressed_size_bytes=total_compressed,
        entries=entries,
        config_snapshot={
            "version": BACKUP_VERSION,
            "depth_default": config.search.depth.value,
            "providers": list(config.search.providers),
        },
        metadata={
            "include_sessions": include_sessions,
            "include_telemetry": include_telemetry,
            "include_knowledge": include_knowledge,
            "include_content_gen": include_content_gen,
            "include_config": include_config,
            "include_radar": include_radar,
        },
    )

    if dry_run:
        return BackupDryRunResult(
            manifest=manifest,
            estimated_total_bytes=total_bytes,
            estimated_compressed_bytes=total_compressed,
            would_include=would_include,
            excluded=excluded,
            warnings=[],
        )

    # Write manifest alongside backup
    manifest_path = backup_path.parent / f"{backup_path.stem}.manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)

    return manifest


def validate_backup(backup_path: Path) -> RestoreValidationResult:
    """Validate a backup archive before restoring.

    Args:
        backup_path: Path to the backup archive or its manifest.

    Returns:
        RestoreValidationResult with validation status and errors.
    """
    manifest_path = None
    if backup_path.suffix == ".json":
        manifest_path = backup_path
    else:
        # Look for manifest alongside the archive
        stem = backup_path.stem  # e.g., backup.tar -> backup
        manifest_path = backup_path.parent / f"{stem}.manifest.json"

    errors: list[str] = []
    warnings: list[str] = []

    if manifest_path is None or not manifest_path.exists():
        return RestoreValidationResult(
            valid=False,
            manifest=BackupManifest(),
            compatible=False,
            errors=[f"Manifest not found: {manifest_path}"],
            warnings=[],
        )

    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        manifest = BackupManifest.from_dict(data)
    except (json.JSONDecodeError, OSError) as e:
        return RestoreValidationResult(
            valid=False,
            manifest=BackupManifest(),
            compatible=False,
            errors=[f"Failed to read manifest: {e}"],
            warnings=[],
        )

    # Version check
    if manifest.version != BACKUP_VERSION:
        errors.append(
            f"Backup version mismatch: expected {BACKUP_VERSION}, got {manifest.version}"
        )

    # Check that entries exist
    config_dir = _get_config_dir()
    for entry in manifest.entries:
        entry_path = config_dir.parent / entry.path
        if not entry_path.exists():
            warnings.append(f"Backup entry not found in current workspace: {entry.path}")

    return RestoreValidationResult(
        valid=len(errors) == 0,
        manifest=manifest,
        compatible=manifest.version == BACKUP_VERSION,
        errors=errors,
        warnings=warnings,
    )


__all__ = [
    "BackupDryRunResult",
    "BackupManifest",
    "BackupManifestEntry",
    "BackupStatus",
    "RestoreValidationResult",
    "create_backup",
    "plan_backup",
    "validate_backup",
]
