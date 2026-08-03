"""Secrets inventory and credential rotation workflow."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from cc_deep_research.config import Config, load_config, load_persisted_config_data
from cc_deep_research.config.credentials import CREDENTIAL_ENV_VARS_BY_FIELD


class CredentialStatus(StrEnum):
    """Credential health status."""

    CONFIGURED = "configured"
    MISSING = "missing"
    STALE = "stale"
    DUPLICATE = "duplicate"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


@dataclass
class CredentialInfo:
    """Information about a configured credential (without exposing the value)."""

    field: str
    provider: str
    status: CredentialStatus
    count: int = 0
    source: str | None = None  # "env" or "file"
    age_days: int | None = None
    warnings: list[str] = field(default_factory=list)
    rotation_guidance: str | None = None


@dataclass
class SecretsInventory:
    """Complete secrets inventory for the dashboard."""

    timestamp: str
    credentials: list[CredentialInfo]
    total_count: int
    healthy_count: int
    warning_count: int
    critical_count: int


# Known secret field paths mapped to providers and rotation guidance
SECRET_FIELD_MAP: dict[str, dict[str, str]] = {
    "tavily.api_keys": {
        "provider": "Tavily",
        "rotation": "Generate new keys at https://app.tavily.com, then update config or set TAVILY_API_KEYS env var",
    },
    "llm.openrouter.api_key": {
        "provider": "OpenRouter",
        "rotation": "Generate new key at https://openrouter.ai/keys, then update config or set OPENROUTER_API_KEY env var",
    },
    "llm.openrouter.api_keys": {
        "provider": "OpenRouter",
        "rotation": "Generate new key at https://openrouter.ai/keys, then update config or set OPENROUTER_API_KEYS env var",
    },
    "llm.cerebras.api_key": {
        "provider": "Cerebras",
        "rotation": "Generate new key at https://cerebras.ai, then update config or set CEREBRAS_API_KEY env var",
    },
    "llm.cerebras.api_keys": {
        "provider": "Cerebras",
        "rotation": "Generate new key at https://cerebras.ai, then update config or set CEREBRAS_API_KEYS env var",
    },
    "llm.anthropic.api_key": {
        "provider": "Anthropic",
        "rotation": "Generate new key at https://console.anthropic.com/settings/keys, then update config or set ANTHROPIC_API_KEY env var",
    },
    "llm.anthropic.api_keys": {
        "provider": "Anthropic",
        "rotation": "Generate new key at https://console.anthropic.com/settings/keys, then update config or set ANTHROPIC_API_KEYS env var",
    },
    "llm.kimi.api_key": {
        "provider": "Kimi",
        "rotation": "Generate a key at https://platform.kimi.ai, then update config or set MOONSHOT_API_KEY",
    },
    "llm.kimi.api_keys": {
        "provider": "Kimi",
        "rotation": "Generate keys at https://platform.kimi.ai, then update config or set MOONSHOT_API_KEYS",
    },
}

CREDENTIAL_ENV_VARS = {
    "tavily.api_keys": ("TAVILY_API_KEYS",),
    **CREDENTIAL_ENV_VARS_BY_FIELD,
}


def _get_secret_source(field: str) -> str | None:
    """Determine if a secret is set via env var or config file."""
    if any(os.environ.get(env_var) for env_var in CREDENTIAL_ENV_VARS.get(field, ())):
        return "env"
    return "file"


def _check_credential_health(
    field: str,
    info: Any,
    *,
    persisted_info: Any = None,
) -> CredentialInfo:
    """Check the health of a single credential."""
    meta = SECRET_FIELD_MAP.get(field, {"provider": field, "rotation": None})
    provider = meta["provider"]

    # Determine count
    count = 0
    if isinstance(info, list):
        count = len(info)
    elif info:
        count = 1

    # Source
    source = _get_secret_source(field)

    # Status
    status = CredentialStatus.CONFIGURED if count == 1 else CredentialStatus.UNKNOWN
    warnings: list[str] = []

    if count == 0:
        status = CredentialStatus.MISSING
        warnings.append(f"No credentials configured for {provider}")
    elif count > 1:
        status = CredentialStatus.DUPLICATE
        warnings.append(f"Multiple credentials ({count}) configured for {provider}")

    # Check for conflict (both env and file)
    env_has = any(os.environ.get(env_var) for env_var in CREDENTIAL_ENV_VARS.get(field, ()))
    file_has = bool(persisted_info)
    if env_has and file_has:
        status = CredentialStatus.CONFLICTING
        warnings.append("Credentials set in both config file and environment variables")

    return CredentialInfo(
        field=field,
        provider=provider,
        status=status,
        count=count,
        source=source,
        age_days=None,
        warnings=warnings,
        rotation_guidance=meta.get("rotation"),
    )


def get_secrets_inventory() -> SecretsInventory:
    """Build a secrets inventory without exposing actual values.

    Returns:
        SecretsInventory with credential health info.
    """
    config = load_config()
    _, persisted_data, _ = load_persisted_config_data()
    persisted_config = Config(**persisted_data)
    credentials: list[CredentialInfo] = []

    secret_values = _collect_secret_values(config)
    persisted_secret_values = _collect_secret_values(persisted_config)

    for field_name, info in secret_values.items():
        cred_info = _check_credential_health(
            field_name,
            info,
            persisted_info=persisted_secret_values[field_name],
        )
        credentials.append(cred_info)

    # Count by status
    healthy = sum(1 for c in credentials if c.status == CredentialStatus.CONFIGURED)
    warnings = sum(
        1
        for c in credentials
        if c.status in (CredentialStatus.DUPLICATE, CredentialStatus.CONFLICTING)
    )
    critical = sum(
        1 for c in credentials if c.status in (CredentialStatus.MISSING, CredentialStatus.STALE)
    )

    return SecretsInventory(
        timestamp=datetime.now(UTC).isoformat(),
        credentials=credentials,
        total_count=len(credentials),
        healthy_count=healthy,
        warning_count=warnings,
        critical_count=critical,
    )


def _collect_secret_values(config: Config) -> dict[str, Any]:
    """Collect configured secret fields without serializing their values."""
    return {
        "tavily.api_keys": config.tavily.api_keys,
        "llm.openrouter.api_key": config.llm.openrouter.api_key,
        "llm.openrouter.api_keys": config.llm.openrouter.api_keys,
        "llm.cerebras.api_key": config.llm.cerebras.api_key,
        "llm.cerebras.api_keys": config.llm.cerebras.api_keys,
        "llm.anthropic.api_key": config.llm.anthropic.api_key,
        "llm.anthropic.api_keys": config.llm.anthropic.api_keys,
        "llm.kimi.api_key": config.llm.kimi.api_key,
        "llm.kimi.api_keys": config.llm.kimi.api_keys,
    }


def get_rotation_guidance() -> list[dict[str, Any]]:
    """Get rotation guidance for all credential types.

    Returns:
        List of guidance dicts per provider.
    """
    inventory = get_secrets_inventory()
    guidance: list[dict[str, Any]] = []

    for cred in inventory.credentials:
        if cred.rotation_guidance:
            guidance.append(
                {
                    "provider": cred.provider,
                    "field": cred.field,
                    "status": cred.status.value,
                    "guidance": cred.rotation_guidance,
                    "count": cred.count,
                    "source": cred.source,
                    "warnings": cred.warnings,
                }
            )

    return guidance


__all__ = [
    "CredentialInfo",
    "CredentialStatus",
    "SecretsInventory",
    "get_rotation_guidance",
    "get_secrets_inventory",
]
