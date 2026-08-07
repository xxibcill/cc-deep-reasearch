"""Environment-backed provider credential overrides."""

from __future__ import annotations

import os

from .credentials import PROVIDER_CREDENTIAL_SPECS, ProviderCredentialSpec
from .schema import Config, _normalize_api_key_list


def provider_api_keys_from_env(spec: ProviderCredentialSpec) -> list[str]:
    """Read one provider's API keys in documented precedence order."""
    values: list[str | list[str]] = []
    for list_env_var, single_env_var in spec.env_var_groups:
        list_value = os.environ.get(list_env_var, "")
        values.append(list_value.split(",") if list_value else [])
        values.append(os.environ.get(single_env_var, ""))
    return _normalize_api_key_list(*values)


def apply_provider_api_key_overrides(config: Config) -> None:
    """Apply all configured provider key aliases to an effective config."""
    for spec in PROVIDER_CREDENTIAL_SPECS:
        api_keys = provider_api_keys_from_env(spec)
        if not api_keys:
            continue
        provider_config = getattr(config.llm, spec.config_attribute)
        provider_config.api_keys = api_keys
        provider_config.api_key = api_keys[0]


__all__ = ["apply_provider_api_key_overrides", "provider_api_keys_from_env"]
