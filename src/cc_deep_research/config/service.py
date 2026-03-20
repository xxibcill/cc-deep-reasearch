"""Shared config mutation and dashboard payload helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .api_models import (
    ConfigFieldError,
    ConfigOverrideConflict,
    ConfigResponse,
    SecretFieldAction,
    SecretFieldMetadata,
    SecretFieldPatch,
)
from .io import load_config, load_persisted_config_data, save_config
from .schema import Config

MASKED_SECRET = "********"

SECRET_FIELD_PATHS = {
    "tavily.api_keys",
    "llm.openrouter.api_key",
    "llm.openrouter.api_keys",
    "llm.cerebras.api_key",
    "llm.cerebras.api_keys",
    "llm.anthropic.api_key",
    "llm.anthropic.api_keys",
}

OVERRIDE_SOURCES = {
    "search.depth": ["CC_DEEP_RESEARCH_DEPTH"],
    "research.default_depth": ["CC_DEEP_RESEARCH_DEPTH"],
    "output.format": ["CC_DEEP_RESEARCH_FORMAT"],
    "display.color": ["NO_COLOR"],
    "tavily.api_keys": ["TAVILY_API_KEYS"],
    "llm.openrouter.api_key": ["OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"],
    "llm.openrouter.api_keys": ["OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"],
    "llm.cerebras.api_key": ["CEREBRAS_API_KEY", "CEREBRAS_API_KEYS"],
    "llm.cerebras.api_keys": ["CEREBRAS_API_KEY", "CEREBRAS_API_KEYS"],
}


class ConfigPatchError(ValueError):
    """Base class for structured patch failures."""

    def __init__(self, *, message: str, fields: list[ConfigFieldError] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or []


class ConfigOverrideError(ConfigPatchError):
    """Raised when a patch targets one or more env-overridden fields."""

    def __init__(self, *, conflicts: list[ConfigOverrideConflict]) -> None:
        super().__init__(
            message="One or more fields are currently overridden by environment variables.",
        )
        self.conflicts = conflicts


@dataclass(slots=True)
class ConfigSnapshot:
    """Resolved config payload state before API serialization."""

    path: Path
    file_exists: bool
    persisted: Config
    effective: Config
    overridden_fields: list[str]
    override_sources: dict[str, list[str]]


def resolve_config_target(config_obj: Config, key: str) -> tuple[Any, str]:
    """Resolve object and final attribute name for a dot-path config key."""
    parts = key.split(".")
    target: Any = config_obj

    for part in parts[:-1]:
        if not hasattr(target, part):
            raise ConfigPatchError(
                message=f"Invalid configuration key: {key}",
                fields=[
                    ConfigFieldError(
                        field=key,
                        code="invalid_key",
                        message=f"Unknown configuration field: {key}",
                    )
                ],
            )
        target = getattr(target, part)

    final_key = parts[-1]
    if not hasattr(target, final_key):
        raise ConfigPatchError(
            message=f"Invalid configuration key: {key}",
            fields=[
                ConfigFieldError(
                    field=key,
                    code="invalid_key",
                    message=f"Unknown configuration field: {key}",
                )
            ],
        )
    return target, final_key


def get_config_snapshot(config_path: Path | None = None) -> ConfigSnapshot:
    """Load persisted and effective config along with override metadata."""
    resolved_path, raw_data, file_exists = load_persisted_config_data(config_path)
    persisted = Config(**raw_data)
    effective = load_config(resolved_path)
    override_sources = _get_active_override_sources()

    return ConfigSnapshot(
        path=resolved_path,
        file_exists=file_exists,
        persisted=persisted,
        effective=effective,
        overridden_fields=sorted(override_sources.keys()),
        override_sources=override_sources,
    )


def build_config_response(config_path: Path | None = None) -> ConfigResponse:
    """Build the dashboard config payload."""
    snapshot = get_config_snapshot(config_path)
    persisted_dump = snapshot.persisted.model_dump(mode="json")
    effective_dump = snapshot.effective.model_dump(mode="json")

    return ConfigResponse(
        config_path=str(snapshot.path),
        file_exists=snapshot.file_exists,
        persisted_config=_mask_secret_values(persisted_dump),
        effective_config=_mask_secret_values(effective_dump),
        overridden_fields=snapshot.overridden_fields,
        override_sources=snapshot.override_sources,
        secret_fields=_build_secret_field_metadata(snapshot),
    )


def update_config(
    updates: dict[str, Any],
    *,
    config_path: Path | None = None,
    save_overridden_fields: bool = False,
) -> ConfigResponse:
    """Apply a partial update, validate it, persist it, and return refreshed state."""
    if not updates:
        raise ConfigPatchError(
            message="No config updates were provided.",
            fields=[
                ConfigFieldError(
                    field="updates",
                    code="missing_updates",
                    message="Provide at least one config field to update.",
                )
            ],
        )

    snapshot = get_config_snapshot(config_path)
    _raise_for_override_conflicts(
        updates=updates,
        override_sources=snapshot.override_sources,
        save_overridden_fields=save_overridden_fields,
    )

    patched = snapshot.persisted.model_dump(mode="python")
    template = snapshot.persisted.model_copy(deep=True)

    for field, value in updates.items():
        target, final_key = resolve_config_target(template, field)
        normalized_value = _normalize_patch_value(getattr(target, final_key), value, field)
        _assign_dict_path(patched, field, normalized_value)

    try:
        validated = Config(**patched)
    except ValidationError as error:
        raise ConfigPatchError(
            message="Config update failed validation.",
            fields=_build_validation_errors(error),
        ) from error

    save_config(validated, snapshot.path)
    return build_config_response(snapshot.path)


def _raise_for_override_conflicts(
    *,
    updates: dict[str, Any],
    override_sources: dict[str, list[str]],
    save_overridden_fields: bool,
) -> None:
    """Reject updates to active env-overridden fields unless explicitly allowed."""
    if save_overridden_fields:
        return

    conflicts = [
        ConfigOverrideConflict(
            field=field,
            env_vars=override_sources[field],
            message="Environment variables currently override this field at runtime.",
        )
        for field in updates
        if field in override_sources
    ]
    if conflicts:
        raise ConfigOverrideError(conflicts=conflicts)


def _get_active_override_sources() -> dict[str, list[str]]:
    """Return only override sources with currently set env vars."""
    import os

    active: dict[str, list[str]] = {}
    for field, env_vars in OVERRIDE_SOURCES.items():
        current = [env_var for env_var in env_vars if os.environ.get(env_var)]
        if current:
            active[field] = current
    return active


def _normalize_patch_value(current_value: Any, value: Any, field: str) -> Any:
    """Normalize secret update operations before full-model validation."""
    if field not in SECRET_FIELD_PATHS:
        return value

    if not isinstance(value, dict):
        raise ConfigPatchError(
            message="Secret fields require an explicit action.",
            fields=[
                ConfigFieldError(
                    field=field,
                    code="invalid_secret_patch",
                    message="Secret fields require {action: replace|clear}.",
                )
            ],
        )

    try:
        patch = SecretFieldPatch.model_validate(value)
    except ValidationError as error:
        raise ConfigPatchError(
            message="Secret field update was invalid.",
            fields=_build_validation_errors(error, field_prefix=field),
        ) from error

    if patch.action == SecretFieldAction.CLEAR:
        return [] if isinstance(current_value, list) else None
    return patch.value


def _assign_dict_path(target: dict[str, Any], field: str, value: Any) -> None:
    """Assign a value into a nested dict using a dot path."""
    parts = field.split(".")
    cursor = target
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def _mask_secret_values(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of config data with secret fields replaced by masked placeholders."""
    masked = deepcopy(data)
    for field in SECRET_FIELD_PATHS:
        _mask_one_secret(masked, field)
    return masked


def _mask_one_secret(data: dict[str, Any], field: str) -> None:
    """Mask a single secret field in-place."""
    parts = field.split(".")
    cursor: Any = data
    for part in parts[:-1]:
        cursor = cursor.get(part)
        if not isinstance(cursor, dict):
            return

    final_key = parts[-1]
    if final_key not in cursor:
        return
    secret_value = cursor[final_key]
    if isinstance(secret_value, list):
        cursor[final_key] = [MASKED_SECRET for _ in secret_value]
        return
    if secret_value:
        cursor[final_key] = MASKED_SECRET


def _build_secret_field_metadata(snapshot: ConfigSnapshot) -> list[SecretFieldMetadata]:
    """Build UI metadata for each masked secret field."""
    persisted_dump = snapshot.persisted.model_dump(mode="python")
    effective_dump = snapshot.effective.model_dump(mode="python")
    metadata: list[SecretFieldMetadata] = []

    for field in sorted(SECRET_FIELD_PATHS):
        persisted_value = _read_dict_path(persisted_dump, field)
        effective_value = _read_dict_path(effective_dump, field)
        metadata.append(
            SecretFieldMetadata(
                field=field,
                persisted_present=_has_secret_value(persisted_value),
                effective_present=_has_secret_value(effective_value),
                persisted_count=_secret_count(persisted_value),
                effective_count=_secret_count(effective_value),
                overridden=field in snapshot.override_sources,
            )
        )

    return metadata


def _read_dict_path(data: dict[str, Any], field: str) -> Any:
    """Read a nested dict value via dot path."""
    current: Any = data
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _has_secret_value(value: Any) -> bool:
    """Return True when a secret-like value is populated."""
    if isinstance(value, list):
        return len(value) > 0
    return value not in (None, "")


def _secret_count(value: Any) -> int:
    """Return the number of configured secret values."""
    if isinstance(value, list):
        return len(value)
    return 1 if _has_secret_value(value) else 0


def _build_validation_errors(
    error: ValidationError,
    *,
    field_prefix: str | None = None,
) -> list[ConfigFieldError]:
    """Convert pydantic validation errors into field-oriented API errors."""
    errors: list[ConfigFieldError] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        field = field_prefix or location
        if field_prefix and location:
            field = field_prefix
        errors.append(
            ConfigFieldError(
                field=field,
                code=str(item["type"]),
                message=item["msg"],
            )
        )
    return errors
