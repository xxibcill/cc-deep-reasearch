"""Authoritative provider credential metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True, slots=True)
class ProviderCredentialSpec:
    """Describe one provider's config location and environment aliases."""

    config_attribute: str
    provider_name: str
    secret_fields: tuple[str, str]
    env_var_groups: tuple[tuple[str, str], ...]

    @property
    def env_vars(self) -> tuple[str, ...]:
        """Return environment aliases in precedence order."""
        return tuple(name for group in self.env_var_groups for name in group)


OPENROUTER_CREDENTIAL_SPEC: Final = ProviderCredentialSpec(
    config_attribute="openrouter",
    provider_name="OpenRouter",
    secret_fields=("llm.openrouter.api_key", "llm.openrouter.api_keys"),
    env_var_groups=(("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"),),
)

CEREBRAS_CREDENTIAL_SPEC: Final = ProviderCredentialSpec(
    config_attribute="cerebras",
    provider_name="Cerebras",
    secret_fields=("llm.cerebras.api_key", "llm.cerebras.api_keys"),
    env_var_groups=(("CEREBRAS_API_KEYS", "CEREBRAS_API_KEY"),),
)

ANTHROPIC_CREDENTIAL_SPEC: Final = ProviderCredentialSpec(
    config_attribute="anthropic",
    provider_name="Anthropic",
    secret_fields=("llm.anthropic.api_key", "llm.anthropic.api_keys"),
    env_var_groups=(("ANTHROPIC_API_KEYS", "ANTHROPIC_API_KEY"),),
)

KIMI_CREDENTIAL_SPEC: Final = ProviderCredentialSpec(
    config_attribute="kimi",
    provider_name="Kimi",
    secret_fields=("llm.kimi.api_key", "llm.kimi.api_keys"),
    env_var_groups=(
        ("MOONSHOT_API_KEYS", "MOONSHOT_API_KEY"),
        ("KIMI_API_KEYS", "KIMI_API_KEY"),
    ),
)

PROVIDER_CREDENTIAL_SPECS: Final = (
    OPENROUTER_CREDENTIAL_SPEC,
    CEREBRAS_CREDENTIAL_SPEC,
    ANTHROPIC_CREDENTIAL_SPEC,
    KIMI_CREDENTIAL_SPEC,
)

CREDENTIAL_ENV_VARS_BY_FIELD: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        field: spec.env_vars
        for spec in PROVIDER_CREDENTIAL_SPECS
        for field in spec.secret_fields
    }
)


__all__ = [
    "ANTHROPIC_CREDENTIAL_SPEC",
    "CEREBRAS_CREDENTIAL_SPEC",
    "CREDENTIAL_ENV_VARS_BY_FIELD",
    "KIMI_CREDENTIAL_SPEC",
    "OPENROUTER_CREDENTIAL_SPEC",
    "PROVIDER_CREDENTIAL_SPECS",
    "ProviderCredentialSpec",
]
