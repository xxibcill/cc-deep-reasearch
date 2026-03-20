"""API contracts for dashboard configuration endpoints."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class SecretFieldAction(StrEnum):
    """Allowed mutation actions for sensitive config fields."""

    REPLACE = "replace"
    CLEAR = "clear"


class SecretFieldPatch(BaseModel):
    """Explicit secret update contract."""

    action: SecretFieldAction
    value: str | list[str] | None = Field(default=None)

    @model_validator(mode="after")
    def validate_value(self) -> SecretFieldPatch:
        """Require a replacement value only when replacing a secret."""
        if self.action == SecretFieldAction.REPLACE and self.value in (None, "", []):
            raise ValueError("replace action requires a non-empty value")
        if self.action == SecretFieldAction.CLEAR and self.value not in (None, "", []):
            raise ValueError("clear action does not accept a value")
        return self


class ConfigFieldError(BaseModel):
    """One field-level config validation or mutation error."""

    field: str
    code: str
    message: str


class ConfigOverrideConflict(BaseModel):
    """Conflict raised when a patch targets an env-overridden field."""

    field: str
    env_vars: list[str]
    message: str


class SecretFieldMetadata(BaseModel):
    """Masking and presence metadata for one secret field."""

    field: str
    persisted_present: bool
    effective_present: bool
    persisted_count: int = 0
    effective_count: int = 0
    overridden: bool = False


class ConfigResponse(BaseModel):
    """Dashboard payload for reading config state."""

    config_path: str
    file_exists: bool
    persisted_config: dict[str, Any]
    effective_config: dict[str, Any]
    overridden_fields: list[str]
    override_sources: dict[str, list[str]]
    secret_fields: list[SecretFieldMetadata]


class ConfigPatchRequest(BaseModel):
    """Dashboard request contract for partial config updates."""

    updates: dict[str, Any]
    save_overridden_fields: bool = False


class ConfigPatchErrorResponse(BaseModel):
    """Structured error payload for failed patch requests."""

    error: str
    fields: list[ConfigFieldError] = Field(default_factory=list)
    conflicts: list[ConfigOverrideConflict] = Field(default_factory=list)
