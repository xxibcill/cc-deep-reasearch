"""Persistent storage for golden benchmark baselines."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cc_deep_research.benchmark import BenchmarkRunReport


def _get_baselines_dir() -> Path:
    """Return the directory for baseline metadata."""
    env = os.environ.get("BENCHMARK_BASELINES_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / ".benchmark_baselines"


def _get_baselines_file() -> Path:
    """Return the baselines metadata JSON file."""
    baselines_dir = _get_baselines_dir()
    baselines_dir.mkdir(parents=True, exist_ok=True)
    return baselines_dir / "baselines.json"


def _load_baseline_registry() -> dict[str, Any]:
    """Load the baseline registry from disk."""
    path = _get_baselines_file()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_baseline_registry(registry: dict[str, Any]) -> None:
    """Save the baseline registry to disk."""
    path = _get_baselines_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, sort_keys=True)


class BaselineMetadata:
    """Metadata for a golden benchmark baseline."""

    def __init__(
        self,
        run_id: str,
        run_path: str,
        owner: str | None = None,
        approved_at: str | None = None,
        approval_note: str | None = None,
        is_promoted: bool = False,
    ):
        self.run_id = run_id
        self.run_path = run_path
        self.owner = owner
        self.approved_at = approved_at or datetime.now(UTC).isoformat()
        self.approval_note = approval_note
        self.is_promoted = is_promoted

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_path": self.run_path,
            "owner": self.owner,
            "approved_at": self.approved_at,
            "approval_note": self.approval_note,
            "is_promoted": self.is_promoted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaselineMetadata:
        return cls(
            run_id=data["run_id"],
            run_path=data["run_path"],
            owner=data.get("owner"),
            approved_at=data.get("approved_at"),
            approval_note=data.get("approval_note"),
            is_promoted=data.get("is_promoted", False),
        )


def list_baselines() -> list[BaselineMetadata]:
    """List all golden baselines."""
    registry = _load_baseline_registry()
    return [BaselineMetadata.from_dict(v) for v in registry.values()]


def get_baseline(run_id: str) -> BaselineMetadata | None:
    """Get a specific baseline by run_id."""
    registry = _load_baseline_registry()
    data = registry.get(run_id)
    if data is None:
        return None
    return BaselineMetadata.from_dict(data)


def promote_to_baseline(
    run_id: str,
    run_path: str,
    owner: str | None = None,
    approval_note: str | None = None,
) -> BaselineMetadata:
    """Promote a benchmark run to golden baseline status."""
    registry = _load_baseline_registry()
    if run_id in registry:
        existing = BaselineMetadata.from_dict(registry[run_id])
        existing.approved_at = datetime.now(UTC).isoformat()
        existing.owner = owner
        existing.approval_note = approval_note
        registry[run_id] = existing.to_dict()
    else:
        metadata = BaselineMetadata(
            run_id=run_id,
            run_path=run_path,
            owner=owner,
            approval_note=approval_note,
            is_promoted=True,
        )
        registry[run_id] = metadata.to_dict()

    _save_baseline_registry(registry)
    return BaselineMetadata.from_dict(registry[run_id])


def demote_baseline(run_id: str) -> bool:
    """Remove golden baseline status from a run. Returns True if found and removed."""
    registry = _load_baseline_registry()
    if run_id not in registry:
        return False
    del registry[run_id]
    _save_baseline_registry(registry)
    return True


def get_promoted_baseline() -> BaselineMetadata | None:
    """Return the currently promoted (active) golden baseline, if any."""
    registry = _load_baseline_registry()
    for data in registry.values():
        if data.get("is_promoted"):
            return BaselineMetadata.from_dict(data)
    return None


def load_baseline_run(run_id: str) -> BenchmarkRunReport | None:
    """Load the full BenchmarkRunReport for a baseline run."""
    registry = _load_baseline_registry()
    data = registry.get(run_id)
    if data is None:
        return None
    run_path = Path(data["run_path"])
    manifest = run_path / "manifest.json"
    if not manifest.exists():
        return None
    with manifest.open("r", encoding="utf-8") as f:
        return BenchmarkRunReport.model_validate(json.load(f))
