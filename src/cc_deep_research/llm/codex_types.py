"""Typed public state and errors for the managed Codex runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

CodexRuntimeStatus: TypeAlias = Literal[
    "stopped",
    "starting",
    "ready",
    "closing",
    "unavailable",
    "error",
]
CodexLoginFlow: TypeAlias = Literal["browser", "device_code"]
CodexLoginStatus: TypeAlias = Literal[
    "pending",
    "canceling",
    "succeeded",
    "failed",
    "canceled",
    "expired",
]
CodexTurnFinishReason: TypeAlias = Literal["completed"]


class CodexRuntimeError(RuntimeError):
    """Base error raised by the managed Codex runtime."""


class CodexRuntimeUnavailableError(CodexRuntimeError):
    """Raised when the local Codex app-server cannot be started or reached."""


class CodexNotAuthenticatedError(CodexRuntimeError):
    """Raised when a Codex turn is requested without an authenticated account."""


class CodexLoginConflictError(CodexRuntimeError):
    """Raised when another interactive Codex login is already active."""


class CodexLoginNotFoundError(CodexRuntimeError):
    """Raised when a login identifier is unknown to this runtime."""


@dataclass(frozen=True, slots=True)
class CodexAccountSnapshot:
    """Safe, immutable account state suitable for API serialization."""

    runtime_status: CodexRuntimeStatus
    authenticated: bool
    requires_openai_auth: bool | None
    account_type: str | None
    email: str | None
    plan_type: str | None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class CodexLoginSnapshot:
    """Safe, immutable state for one managed interactive login."""

    login_id: str
    flow: CodexLoginFlow
    status: CodexLoginStatus
    auth_url: str | None
    verification_url: str | None
    user_code: str | None
    error: str | None
    created_at: str
    completed_at: str | None


@dataclass(frozen=True, slots=True)
class CodexTurnResult:
    """Provider-neutral result returned by the managed runtime."""

    content: str
    model: str
    turn_id: str
    duration_ms: int
    finish_reason: CodexTurnFinishReason
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_output_tokens: int = 0


__all__ = [
    "CodexAccountSnapshot",
    "CodexLoginConflictError",
    "CodexLoginFlow",
    "CodexLoginNotFoundError",
    "CodexLoginSnapshot",
    "CodexLoginStatus",
    "CodexNotAuthenticatedError",
    "CodexRuntimeError",
    "CodexRuntimeStatus",
    "CodexRuntimeUnavailableError",
    "CodexTurnFinishReason",
    "CodexTurnResult",
]
