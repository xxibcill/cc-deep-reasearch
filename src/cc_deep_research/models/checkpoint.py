"""Durable checkpoint models for workflow step persistence and resume.

This module defines the checkpoint contract for research workflow steps,
enabling restartable and debuggable execution at step granularity.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


CHECKPOINT_SCHEMA_VERSION = "1.0.0"


class CheckpointPhase(StrEnum):
    """Standard phases where checkpoints are created."""

    SESSION_START = "session_start"
    TEAM_INIT = "team_init"
    STRATEGY = "strategy"
    QUERY_EXPANSION = "query_expansion"
    SOURCE_COLLECTION = "source_collection"
    ANALYSIS = "analysis"
    DEEP_ANALYSIS = "deep_analysis"
    VALIDATION = "validation"
    ITERATION_DECISION = "iteration_decision"
    ITERATION_COLLECTION = "iteration_collection"
    SESSION_COMPLETE = "session_complete"
    SESSION_INTERRUPTED = "session_interrupted"


class CheckpointStatus(StrEnum):
    """Status of a checkpoint."""

    PENDING = "pending"  # Checkpoint creation in progress
    COMMITTED = "committed"  # Checkpoint persisted successfully
    FAILED = "failed"  # Checkpoint creation failed


class CheckpointOperation(StrEnum):
    """Operations that create checkpoints."""

    INITIALIZE = "initialize"
    EXECUTE = "execute"
    ITERATE = "iterate"
    FINALIZE = "finalize"
    INTERRUPT = "interrupt"


class ArtifactRef(BaseModel):
    """Reference to a persisted artifact."""

    kind: str = Field(..., description="Artifact type (session, report, fixture, state)")
    path: str = Field(..., description="Relative path to the artifact")
    content_hash: str | None = Field(default=None, description="SHA-256 hash of content")
    size_bytes: int | None = Field(default=None, description="Artifact size in bytes")
    included_in_bundle: bool = Field(default=False, description="Whether included in trace bundle")


class ProviderFixtureRef(BaseModel):
    """Reference to a captured provider response fixture."""

    provider: str = Field(..., description="Provider name (tavily, claude, etc.)")
    query_hash: str = Field(..., description="Hash of the query/request")
    captured_at: str = Field(..., description="ISO timestamp when fixture was captured")
    response_path: str | None = Field(default=None, description="Path to captured response")
    live_fallback_allowed: bool = Field(default=True, description="Whether live calls are allowed if fixture missing")


class StepInputRef(BaseModel):
    """Reference to normalized step inputs."""

    ref_type: str = Field(default="inline", description="Reference type (inline, file, hash)")
    ref_value: str | dict[str, Any] = Field(..., description="Reference value or inline data")
    content_hash: str | None = Field(default=None, description="Hash of referenced content")


class StepOutputRef(BaseModel):
    """Reference to normalized step outputs."""

    ref_type: str = Field(default="inline", description="Reference type (inline, file, hash)")
    ref_value: str | dict[str, Any] = Field(..., description="Reference value or inline data")
    content_hash: str | None = Field(default=None, description="Hash of referenced content")


class Checkpoint(BaseModel):
    """Durable checkpoint for a workflow step.

    Captures enough context to:
    - Inspect exact inputs and outputs of a step
    - Rerun one step without rerunning entire workflow
    - Resume a failed/interrupted run from latest valid checkpoint
    - Replay a completed run from selected checkpoint for debugging
    """

    # Core identity
    checkpoint_id: str = Field(default_factory=lambda: f"cp-{uuid4().hex[:12]}")
    session_id: str = Field(..., description="Associated research session ID")
    trace_version: str = Field(default="1.0.0", description="Trace schema version")
    checkpoint_version: str = Field(default=CHECKPOINT_SCHEMA_VERSION, description="Checkpoint schema version")
    sequence_number: int = Field(..., description="Monotonic sequence within session")

    # Timing
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp")

    # Phase context
    phase: CheckpointPhase = Field(..., description="Workflow phase")
    operation: CheckpointOperation = Field(..., description="Operation type")
    attempt: int = Field(default=1, description="Attempt number for retries")
    iteration: int | None = Field(default=None, description="Iteration number for iterative workflows")

    # Status
    status: CheckpointStatus = Field(default=CheckpointStatus.PENDING, description="Checkpoint status")

    # Lineage
    resume_token: str = Field(..., description="Token for resuming from this checkpoint")
    parent_checkpoint_id: str | None = Field(default=None, description="Previous checkpoint in lineage")
    cause_event_id: str | None = Field(default=None, description="Event that triggered this checkpoint")

    # Input/output references
    input_ref: StepInputRef | None = Field(default=None, description="Reference to step inputs")
    output_ref: StepOutputRef | None = Field(default=None, description="Reference to step outputs")
    state_ref: str | None = Field(default=None, description="Reference to session state snapshot")
    config_ref: str | None = Field(default=None, description="Reference to config snapshot")

    # Artifact references
    artifact_refs: list[ArtifactRef] = Field(default_factory=list, description="References to persisted artifacts")
    provider_fixture_refs: list[ProviderFixtureRef] = Field(default_factory=list, description="References to provider fixtures")

    # Replayability
    replayable: bool = Field(default=True, description="Whether this step can be replayed exactly")
    replayable_reason: str | None = Field(default=None, description="Reason if not replayable")
    resume_safe: bool = Field(default=False, description="Whether safe to resume from this checkpoint")
    resume_prerequisites: list[str] = Field(default_factory=list, description="Required checkpoint IDs to resume")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional checkpoint metadata")

    def mark_committed(self) -> Checkpoint:
        """Mark checkpoint as committed after successful persistence."""
        return self.model_copy(update={"status": CheckpointStatus.COMMITTED})

    def mark_failed(self, reason: str) -> Checkpoint:
        """Mark checkpoint as failed with reason."""
        return self.model_copy(update={
            "status": CheckpointStatus.FAILED,
            "replayable": False,
            "replayable_reason": reason,
        })

    def mark_resume_safe(self) -> Checkpoint:
        """Mark checkpoint as safe for resume after verifying all refs."""
        return self.model_copy(update={"resume_safe": True})

    def with_output(self, output: StepOutputRef) -> Checkpoint:
        """Attach output reference to checkpoint."""
        return self.model_copy(update={"output_ref": output})


class CheckpointManifest(BaseModel):
    """Manifest of all checkpoints for a session."""

    session_id: str = Field(..., description="Session ID")
    schema_version: str = Field(default=CHECKPOINT_SCHEMA_VERSION, description="Manifest schema version")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Checkpoint inventory
    checkpoints: list[Checkpoint] = Field(default_factory=list, description="All checkpoints in sequence")

    # Resume info
    latest_resume_safe_checkpoint_id: str | None = Field(default=None, description="Latest safe resume point")
    latest_checkpoint_id: str | None = Field(default=None, description="Latest checkpoint regardless of resume safety")

    def add_checkpoint(self, checkpoint: Checkpoint) -> CheckpointManifest:
        """Add a checkpoint and update manifest metadata."""
        checkpoints = list(self.checkpoints) + [checkpoint]
        latest_id = checkpoint.checkpoint_id
        latest_resume_safe = (
            checkpoint.checkpoint_id
            if checkpoint.resume_safe and checkpoint.status == CheckpointStatus.COMMITTED
            else self.latest_resume_safe_checkpoint_id
        )
        return self.model_copy(update={
            "checkpoints": checkpoints,
            "latest_checkpoint_id": latest_id,
            "latest_resume_safe_checkpoint_id": latest_resume_safe,
            "updated_at": datetime.utcnow().isoformat(),
        })

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Get a checkpoint by ID."""
        for cp in self.checkpoints:
            if cp.checkpoint_id == checkpoint_id:
                return cp
        return None

    def get_checkpoints_by_phase(self, phase: CheckpointPhase) -> list[Checkpoint]:
        """Get all checkpoints for a phase."""
        return [cp for cp in self.checkpoints if cp.phase == phase]

    def get_resume_lineage(self, from_checkpoint_id: str) -> list[Checkpoint]:
        """Get checkpoint lineage from start to specified checkpoint."""
        lineage = []
        current = self.get_checkpoint(from_checkpoint_id)
        while current:
            lineage.append(current)
            if current.parent_checkpoint_id:
                current = self.get_checkpoint(current.parent_checkpoint_id)
            else:
                current = None
        return list(reversed(lineage))


class ResumeRequest(BaseModel):
    """Request to resume a session from a checkpoint."""

    session_id: str = Field(..., description="Session to resume")
    checkpoint_id: str | None = Field(default=None, description="Specific checkpoint (default: latest safe)")
    mode: str = Field(default="resume_latest", description="Resume mode: resume_latest, resume_from_checkpoint, rerun_step, debug_replay")

    # Config options
    config_pinned: bool = Field(default=True, description="Pin config to original values")
    config_overrides: dict[str, Any] = Field(default_factory=dict, description="Config overrides with explicit record")
    live_provider_access: bool = Field(default=False, description="Allow live provider calls")
    artifact_reuse: bool = Field(default=True, description="Reuse existing artifacts vs force rebuild")
    use_fixtures: bool = Field(default=True, description="Use captured fixtures where available")


class ResumeResult(BaseModel):
    """Result of a resume operation."""

    success: bool = Field(..., description="Whether resume succeeded")
    session_id: str = Field(..., description="New or resumed session ID")
    original_session_id: str = Field(..., description="Original session being resumed")
    resumed_from_checkpoint_id: str = Field(..., description="Checkpoint used for resume")
    resume_mode: str = Field(..., description="Mode used for resume")

    # Lineage tracking
    checkpoint_lineage: list[str] = Field(default_factory=list, description="Parent checkpoint IDs")
    new_checkpoint_id: str | None = Field(default=None, description="New checkpoint created")

    # Status
    message: str | None = Field(default=None, description="Human-readable status message")
    error: str | None = Field(default=None, description="Error message if failed")


class RerunStepRequest(BaseModel):
    """Request to rerun a single step from a checkpoint."""

    session_id: str = Field(..., description="Session ID")
    checkpoint_id: str = Field(..., description="Checkpoint to rerun from")

    # Rerun options
    use_persisted_inputs: bool = Field(default=True, description="Use persisted inputs vs fresh")
    use_fixtures: bool = Field(default=True, description="Use captured provider fixtures")
    allow_live_fallback: bool = Field(default=False, description="Allow live provider calls if fixtures missing")
    config_overrides: dict[str, Any] = Field(default_factory=dict, description="Config overrides")


class RerunStepResult(BaseModel):
    """Result of a step rerun operation."""

    success: bool = Field(..., description="Whether rerun succeeded")
    session_id: str = Field(..., description="Session ID")
    checkpoint_id: str = Field(..., description="Original checkpoint ID")
    new_checkpoint_id: str | None = Field(default=None, description="New checkpoint from rerun")

    # Comparison
    output_match: bool | None = Field(default=None, description="Whether outputs match original")
    output_diff: dict[str, Any] | None = Field(default=None, description="Diff between original and new output")

    # Status
    message: str | None = Field(default=None, description="Human-readable status message")
    error: str | None = Field(default=None, description="Error message if failed")


__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "ArtifactRef",
    "Checkpoint",
    "CheckpointManifest",
    "CheckpointOperation",
    "CheckpointPhase",
    "CheckpointStatus",
    "ProviderFixtureRef",
    "RerunStepRequest",
    "RerunStepResult",
    "ResumeRequest",
    "ResumeResult",
    "StepInputRef",
    "StepOutputRef",
]
