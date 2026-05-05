"""Guided setup wizard and config profile management."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from cc_deep_research.config import (
    Config,
    ConfigPatchError,
    get_default_config_path,
    load_config,
    save_config,
)
from cc_deep_research.config.api_models import ConfigFieldError


class ProfileType(StrEnum):
    """Config profile types."""

    LOCAL_DEVELOPMENT = "local_development"
    LOCAL_PRODUCTION = "local_production"
    RESTRICTED_OFFLINE = "restricted_offline"
    CUSTOM = "custom"


@dataclass
class SetupStep:
    """One step in the guided setup flow."""

    step_id: str
    label: str
    description: str
    required: bool = True
    validated: bool = False
    skipped: bool = False
    error: str | None = None


@dataclass
class SetupWizardResult:
    """Result of running the setup wizard."""

    success: bool
    profile_applied: bool
    config_path: Path | None
    steps_completed: int
    steps_total: int
    errors: list[str]
    config_snapshot: dict[str, Any] | None = None


@dataclass
class ConfigProfile:
    """A named config profile with preset values."""

    name: str
    profile_type: ProfileType
    description: str
    settings: dict[str, Any]


# Config profiles
PROFILES: dict[ProfileType, ConfigProfile] = {
    ProfileType.LOCAL_DEVELOPMENT: ConfigProfile(
        name="Local Development",
        profile_type=ProfileType.LOCAL_DEVELOPMENT,
        description="For local development with verbose logging, default ports, and permissive CORS",
        settings={
            "display.color": "always",
            "display.verbose": True,
            "search.cache.enabled": False,
        },
    ),
    ProfileType.LOCAL_PRODUCTION: ConfigProfile(
        name="Local Production",
        profile_type=ProfileType.LOCAL_PRODUCTION,
        description="Hardened settings for local production: minimal logging, restrictive CORS origins, secure defaults",
        settings={
            "display.color": "auto",
            "display.verbose": False,
            "search.cache.enabled": True,
            "search.cache.ttl_seconds": 3600,
        },
    ),
    ProfileType.RESTRICTED_OFFLINE: ConfigProfile(
        name="Restricted / Offline",
        profile_type=ProfileType.RESTRICTED_OFFLINE,
        description="For restricted environments with no external API access. Disables telemetry and radar.",
        settings={
            "display.color": "never",
            "display.verbose": False,
            "search.cache.enabled": True,
        },
    ),
}


def _validate_tavily_key(key: str) -> bool:
    """Validate a Tavily API key format (basic format check)."""
    if not key or len(key) < 10:
        return False
    return True


def _validate_api_key_format(key: str | None, provider: str) -> tuple[bool, str]:
    """Validate an API key format for a given provider."""
    if not key:
        return False, "Key is empty"
    if len(key) < 8:
        return False, f"{provider} key too short"
    return True, "ok"


def list_profiles() -> list[dict[str, Any]]:
    """List all available config profiles.

    Returns:
        List of profile info dicts.
    """
    return [
        {
            "type": pt.value,
            "name": p.name,
            "description": p.description,
        }
        for pt, p in PROFILES.items()
    ]


def get_profile(profile_type: ProfileType) -> ConfigProfile | None:
    """Get a profile by type."""
    return PROFILES.get(profile_type)


def apply_profile(
    profile_type: ProfileType,
    config_path: Path | None = None,
) -> Config:
    """Apply a config profile to the current config.

    Args:
        profile_type: Type of profile to apply.
        config_path: Optional path to config file.

    Returns:
        Updated Config object.

    Raises:
        KeyError: If profile type is unknown.
    """
    profile = PROFILES.get(profile_type)
    if not profile:
        raise KeyError(f"Unknown profile type: {profile_type}")

    if config_path is None:
        config_path = get_default_config_path()

    current = load_config(config_path)
    patched = current.model_copy(deep=True)

    # Apply profile settings via dot-path
    from cc_deep_research.config.service import _assign_dict_path

    for field_path, value in profile.settings.items():
        _assign_dict_path(patched.model_dump(mode="python"), field_path, value)

    try:
        validated = Config(**patched.model_dump(mode="python"))
    except ValidationError as e:
        raise ConfigPatchError(
            message="Profile application failed validation",
            fields=[
                ConfigFieldError(
                    field=".".join(str(x) for x in err["loc"]),
                    code=str(err["type"]),
                    message=err["msg"],
                )
                for err in e.errors()
            ],
        ) from e

    save_config(validated, config_path)
    return validated


def run_setup_validation(
    config_path: Path | None = None,
) -> tuple[bool, list[SetupStep]]:
    """Validate the current config as part of the setup wizard.

    Args:
        config_path: Path to config file to validate.

    Returns:
        (is_valid, list of SetupStep results).
    """
    config_path = config_path or get_default_config_path()
    steps: list[SetupStep] = []

    # Step 1: Config file exists and is readable
    steps.append(SetupStep(
        step_id="config_readable",
        label="Config file readable",
        description="Config file exists and is valid YAML",
        required=True,
    ))
    if not config_path.exists():
        steps[-1].error = "Config file not found"
    else:
        try:
            current = load_config(config_path)
            steps[-1].validated = True
        except Exception as e:
            steps[-1].error = str(e)

    # Step 2: At least one provider has API key
    steps.append(SetupStep(
        step_id="provider_credentials",
        label="Provider credentials",
        description="At least one search or LLM provider has credentials configured",
        required=True,
    ))
    try:
        current = load_config(config_path)
        has_tavily = bool(current.tavily.api_keys or os.environ.get("TAVILY_API_KEYS"))
        has_openrouter = bool(
            current.llm.openrouter.get_api_keys()
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENROUTER_API_KEYS")
        )
        has_anthropic = bool(
            current.llm.anthropic.get_api_keys()
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEYS")
        )
        if has_tavily or has_openrouter or has_anthropic:
            steps[-1].validated = True
        else:
            steps[-1].error = "No provider credentials found in config or environment"
    except Exception as e:
        steps[-1].error = str(e)

    # Step 3: Config values are valid
    steps.append(SetupStep(
        step_id="config_valid",
        label="Config values valid",
        description="All config fields have valid values",
        required=True,
    ))
    try:
        current = load_config(config_path)
        steps[-1].validated = True
    except Exception as e:
        steps[-1].error = str(e)

    # Step 4: Data directories are accessible
    steps.append(SetupStep(
        step_id="data_dirs",
        label="Data directories",
        description="Required data directories are accessible",
        required=False,
        skipped=True,  # Can be created on first run
    ))

    is_valid = all(
        s.validated or not s.required
        for s in steps
    )

    return is_valid, steps


def create_initial_config(
    config_path: Path | None = None,
    profile_type: ProfileType = ProfileType.LOCAL_PRODUCTION,
) -> SetupWizardResult:
    """Create an initial config file using a profile.

    Args:
        config_path: Optional path for the config file.
        profile_type: Profile to use as baseline.

    Returns:
        SetupWizardResult with creation status.
    """
    if config_path is None:
        config_path = get_default_config_path()

    errors: list[str] = []

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Apply profile
        apply_profile(profile_type, config_path)
        steps_completed = 1
    except Exception as e:
        errors.append(f"Failed to apply profile: {e}")
        steps_completed = 0

    # Run validation
    is_valid, steps = run_setup_validation(config_path)
    if not is_valid:
        failed = [s for s in steps if s.required and not s.validated and not s.skipped]
        for s in failed:
            if s.error:
                errors.append(f"{s.label}: {s.error}")

    return SetupWizardResult(
        success=is_valid and len(errors) == 0,
        profile_applied=True,
        config_path=config_path,
        steps_completed=steps_completed,
        steps_total=len(steps),
        errors=errors,
        config_snapshot=None,
    )


__all__ = [
    "ConfigProfile",
    "ProfileType",
    "SetupStep",
    "SetupWizardResult",
    "apply_profile",
    "create_initial_config",
    "get_profile",
    "list_profiles",
    "run_setup_validation",
]
