"""Durable, validated state for resuming interrupted research runs."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from cc_deep_research.config import Config
from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    PlannerResult,
    PlanSynthesis,
    ResearchDepth,
    SearchResultItem,
    StrategyResult,
    TaskExecutionResult,
    ValidationResult,
)
from cc_deep_research.persistence import atomic_write_json
from cc_deep_research.research_runs.models import ResearchRunRequest, ResearchWorkflow
from cc_deep_research.telemetry import get_default_telemetry_dir

RESUME_SNAPSHOT_SCHEMA_VERSION = "2.0.0"
_SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS) or (
        normalized in {"token", "tokens"}
        or normalized.endswith("_token")
        or (
            normalized.endswith("_tokens")
            and not normalized.startswith(("max_", "min_"))
        )
    )


class ResearchResumePhase(StrEnum):
    """The next durable workflow boundary to execute."""

    STRATEGY = "strategy"
    QUERY_EXPANSION = "query_expansion"
    SOURCE_COLLECTION = "source_collection"
    ANALYSIS = "analysis"
    COMPLETE = "complete"
    PLANNER_PLAN = "planner_plan"
    PLANNER_EXECUTION = "planner_execution"
    PLANNER_SYNTHESIS = "planner_synthesis"


class ResearchResumeState(BaseModel):
    """Complete serializable workflow state at one safe resume boundary."""

    schema_version: str = RESUME_SNAPSHOT_SCHEMA_VERSION
    workflow: ResearchWorkflow
    query: str = Field(min_length=1)
    depth: ResearchDepth
    min_sources: int | None = Field(default=None, ge=1)
    next_phase: ResearchResumePhase
    request: ResearchRunRequest
    config_fingerprint: str = Field(min_length=64, max_length=64)
    strategy: StrategyResult | None = None
    sources: list[SearchResultItem] = Field(default_factory=list)
    analysis: AnalysisResult | None = None
    validation: ValidationResult | None = None
    iteration_history: list[IterationHistoryRecord] = Field(default_factory=list)
    iteration: int = Field(default=1, ge=1)
    follow_up_queries: list[str] = Field(default_factory=list)
    planner_result: PlannerResult | None = None
    planner_task_results: dict[str, TaskExecutionResult] = Field(default_factory=dict)
    planner_synthesis: PlanSynthesis | None = None
    origin_session_id: str | None = None
    origin_checkpoint_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_phase_prerequisites(self) -> ResearchResumeState:
        """Reject snapshots that cannot execute their declared next phase."""
        if self.schema_version != RESUME_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"unsupported resume state schema: {self.schema_version}")
        if self.request.query != self.query:
            raise ValueError("resume request query must match snapshot query")
        if self.request.workflow != self.workflow:
            raise ValueError("resume request workflow must match snapshot workflow")

        if self.workflow == ResearchWorkflow.STAGED:
            staged_phases = {
                ResearchResumePhase.STRATEGY,
                ResearchResumePhase.QUERY_EXPANSION,
                ResearchResumePhase.SOURCE_COLLECTION,
                ResearchResumePhase.ANALYSIS,
                ResearchResumePhase.COMPLETE,
            }
            if self.next_phase not in staged_phases:
                raise ValueError(f"{self.next_phase.value} is not a staged workflow phase")
            phases_requiring_strategy = {
                ResearchResumePhase.QUERY_EXPANSION,
                ResearchResumePhase.SOURCE_COLLECTION,
                ResearchResumePhase.ANALYSIS,
                ResearchResumePhase.COMPLETE,
            }
            if self.next_phase in phases_requiring_strategy and self.strategy is None:
                raise ValueError(f"strategy is required before {self.next_phase.value}")
            if self.next_phase == ResearchResumePhase.COMPLETE and self.analysis is None:
                raise ValueError("analysis is required before completion")
            return self

        planner_phases = {
            ResearchResumePhase.PLANNER_PLAN,
            ResearchResumePhase.PLANNER_EXECUTION,
            ResearchResumePhase.PLANNER_SYNTHESIS,
            ResearchResumePhase.COMPLETE,
        }
        if self.next_phase not in planner_phases:
            raise ValueError(f"{self.next_phase.value} is not a planner workflow phase")
        planner_phases_requiring_plan = {
            ResearchResumePhase.PLANNER_EXECUTION,
            ResearchResumePhase.PLANNER_SYNTHESIS,
            ResearchResumePhase.COMPLETE,
        }
        if self.next_phase in planner_phases_requiring_plan and self.planner_result is None:
            raise ValueError(f"planner_result is required before {self.next_phase.value}")
        if self.next_phase == ResearchResumePhase.COMPLETE and self.planner_synthesis is None:
            raise ValueError("planner_synthesis is required before completion")
        return self


class ResearchResumeSnapshotRef(BaseModel):
    """Reference to one checksum-protected resume snapshot."""

    path: str
    content_hash: str
    size_bytes: int = Field(ge=1)


class ResearchResumeSnapshotError(RuntimeError):
    """Raised when a resume snapshot is missing, corrupt, or incompatible."""


def _redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _redact_sensitive_values(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            if _is_sensitive_key(key):
                result[key] = "<redacted>"
            else:
                result[key] = _redact_sensitive_values(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_redact_sensitive_values(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def build_config_fingerprint(config: Config | Mapping[str, Any]) -> str:
    """Hash execution-affecting configuration without retaining secret values."""
    payload = config.model_dump(mode="python") if isinstance(config, Config) else dict(config)
    safe_payload = _redact_sensitive_values(payload)
    return hashlib.sha256(_canonical_json(safe_payload).encode("utf-8")).hexdigest()


class ResearchResumeStore:
    """Persist and validate resume snapshots within telemetry session folders."""

    def __init__(self, telemetry_dir: Path | None = None) -> None:
        self._telemetry_dir = telemetry_dir or get_default_telemetry_dir()

    @property
    def telemetry_dir(self) -> Path:
        return self._telemetry_dir

    def save(self, session_id: str, state: ResearchResumeState) -> ResearchResumeSnapshotRef:
        """Persist a snapshot atomically and return its stable reference."""
        state_payload = state.model_dump(mode="json")
        content_hash = hashlib.sha256(_canonical_json(state_payload).encode("utf-8")).hexdigest()
        relative_path = Path("resume") / f"state-{uuid.uuid4().hex[:12]}.json"
        snapshot_path = self._session_path(session_id) / relative_path
        envelope = {
            "schema_version": RESUME_SNAPSHOT_SCHEMA_VERSION,
            "content_hash": content_hash,
            "state": state_payload,
        }
        atomic_write_json(snapshot_path, envelope)
        return ResearchResumeSnapshotRef(
            path=relative_path.as_posix(),
            content_hash=content_hash,
            size_bytes=snapshot_path.stat().st_size,
        )

    def load(self, session_id: str, state_ref: str) -> ResearchResumeState:
        """Load a snapshot after validating path, schema, and checksum."""
        snapshot_path = self._resolve_reference(session_id, state_ref)
        try:
            envelope = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ResearchResumeSnapshotError(f"Resume snapshot not found: {state_ref}") from exc
        except (json.JSONDecodeError, OSError) as exc:
            raise ResearchResumeSnapshotError(f"Resume snapshot is unreadable: {state_ref}") from exc

        if envelope.get("schema_version") != RESUME_SNAPSHOT_SCHEMA_VERSION:
            raise ResearchResumeSnapshotError(
                f"Unsupported resume snapshot schema: {envelope.get('schema_version')}"
            )
        state_payload = envelope.get("state")
        if not isinstance(state_payload, dict):
            raise ResearchResumeSnapshotError("Resume snapshot state is missing")
        actual_hash = hashlib.sha256(_canonical_json(state_payload).encode("utf-8")).hexdigest()
        if actual_hash != envelope.get("content_hash"):
            raise ResearchResumeSnapshotError("Resume snapshot checksum does not match")
        try:
            return ResearchResumeState.model_validate(state_payload)
        except ValueError as exc:
            raise ResearchResumeSnapshotError(f"Resume snapshot is invalid: {exc}") from exc

    def _session_path(self, session_id: str) -> Path:
        if not session_id or Path(session_id).name != session_id:
            raise ResearchResumeSnapshotError("Invalid session identifier")
        return self._telemetry_dir / session_id

    def _resolve_reference(self, session_id: str, state_ref: str) -> Path:
        session_path = self._session_path(session_id).resolve()
        candidate = (session_path / state_ref).resolve()
        try:
            candidate.relative_to(session_path)
        except ValueError as exc:
            raise ResearchResumeSnapshotError("Invalid resume snapshot reference") from exc
        if candidate.parent.name != "resume" or candidate.suffix != ".json":
            raise ResearchResumeSnapshotError("Invalid resume snapshot reference")
        return candidate


__all__ = [
    "RESUME_SNAPSHOT_SCHEMA_VERSION",
    "ResearchResumePhase",
    "ResearchResumeSnapshotError",
    "ResearchResumeSnapshotRef",
    "ResearchResumeState",
    "ResearchResumeStore",
    "build_config_fingerprint",
]
