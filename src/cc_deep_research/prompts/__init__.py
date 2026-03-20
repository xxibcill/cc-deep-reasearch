"""Prompt override models and registry for LLM-backed agents.

This module provides models for customizing agent prompts at runtime,
enabling operators to tailor LLM behavior for specialized research tasks.

V1 Scope: LLM-backed agents only (analyzer, deep_analyzer, report_quality_evaluator).
Heuristic-only agents (lead, expander, validator) are deferred to V2.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Supported agent IDs for prompt overrides (V1: LLM-backed agents only)
SUPPORTED_PROMPT_AGENTS: set[str] = {"analyzer", "deep_analyzer", "report_quality_evaluator"}

AgentId = Literal["analyzer", "deep_analyzer", "report_quality_evaluator"]


class AgentPromptOverride(BaseModel):
    """Prompt override configuration for a single agent.

    Attributes:
        system_prompt: Complete replacement for the default system prompt.
        prompt_prefix: Text to prepend to the default prompt (for extending behavior).
    """

    system_prompt: str | None = Field(
        default=None,
        description="Complete replacement for the default system prompt",
    )
    prompt_prefix: str | None = Field(
        default=None,
        description="Text to prepend to the default prompt for extending behavior",
    )

    @field_validator("system_prompt", "prompt_prefix")
    @classmethod
    def strip_whitespace(cls, value: str | None) -> str | None:
        """Strip whitespace-only values to None."""
        if value is None or not value.strip():
            return None
        return value.strip()


class PromptOverrides(BaseModel):
    """Collection of prompt overrides for multiple agents.

    Attributes:
        overrides: Mapping of agent ID to prompt override configuration.
    """

    overrides: dict[str, AgentPromptOverride] = Field(default_factory=dict)

    @field_validator("overrides")
    @classmethod
    def validate_agent_ids(cls, v: dict[str, AgentPromptOverride]) -> dict[str, AgentPromptOverride]:
        """Validate that all agent IDs are supported."""
        unknown = set(v.keys()) - SUPPORTED_PROMPT_AGENTS
        if unknown:
            raise ValueError(f"Unknown agent ids: {unknown}. Supported: {SUPPORTED_PROMPT_AGENTS}")
        return v

    def is_empty(self) -> bool:
        """Check if any overrides are configured."""
        return not any(
            override.system_prompt or override.prompt_prefix
            for override in self.overrides.values()
        )


class PromptRegistry:
    """Registry for managing agent prompts with override support.

    This class provides:
    - Default prompt storage and retrieval
    - Override resolution with merge semantics
    - Validation of agent IDs and override configurations
    """

    def __init__(
        self,
        *,
        system_prompts: dict[str, str] | None = None,
        operation_prompts: dict[str, dict[str, str]] | None = None,
    ) -> None:
        """Initialize the prompt registry.

        Args:
            system_prompts: Optional custom default system prompts.
            operation_prompts: Optional custom default operation prompts.
        """
        # Store defaults
        self._system_prompts = system_prompts or {}
        self._operation_prompts = operation_prompts or {}
        self._overrides: dict[str, AgentPromptOverride] = {}

    def apply_overrides(self, overrides: PromptOverrides | None) -> None:
        """Apply prompt overrides from a PromptOverrides model.

        Args:
            overrides: The overrides to apply, or None to clear all overrides.
        """
        self._overrides = {}
        if overrides is None or overrides.is_empty():
            return

        for agent_id, override in overrides.overrides.items():
            if override.system_prompt or override.prompt_prefix:
                self._overrides[agent_id] = override

    def apply_raw_overrides(
        self,
        overrides: dict[str, dict[str, str | None]] | None,
    ) -> None:
        """Apply prompt overrides from a raw dictionary.

        This is a convenience method for integrating with the request model.

        Args:
            overrides: Raw dictionary of agent_id -> {system_prompt, prompt_prefix}.
        """
        self._overrides = {}
        if not overrides:
            return

        for agent_id, raw_override in overrides.items():
            if agent_id not in SUPPORTED_PROMPT_AGENTS:
                continue
            system_prompt = raw_override.get("system_prompt")
            prompt_prefix = raw_override.get("prompt_prefix")
            # Strip whitespace-only values
            if system_prompt and not system_prompt.strip():
                system_prompt = None
            if prompt_prefix and not prompt_prefix.strip():
                prompt_prefix = None
            if system_prompt or prompt_prefix:
                self._overrides[agent_id] = AgentPromptOverride(
                    system_prompt=system_prompt,
                    prompt_prefix=prompt_prefix,
                )

    def resolve_prompt(
        self,
        agent_id: str,
        operation: str,  # noqa: ARG002
    ) -> tuple[str, str | None, bool]:
        """Resolve the effective prompt configuration for an agent/operation.

        Args:
            agent_id: The agent identifier (e.g., "analyzer").
            operation: The operation name (e.g., "extract_themes").

        Returns:
            Tuple of (system_prompt, prompt_prefix, used_override).
        """
        override = self._overrides.get(agent_id)
        used_override = False

        # Resolve system prompt
        if override and override.system_prompt:
            system_prompt = override.system_prompt
            used_override = True
        else:
            system_prompt = self._system_prompts.get(agent_id, "")

        # Resolve prompt prefix
        prompt_prefix = None
        if override and override.prompt_prefix:
            prompt_prefix = override.prompt_prefix
            used_override = True

        return system_prompt, prompt_prefix, used_override

    def get_effective_overrides(self) -> dict[str, dict[str, str | None]]:
        """Get the currently effective overrides as a raw dictionary.

        Returns:
            Dictionary mapping agent_id to {system_prompt, prompt_prefix}.
        """
        result: dict[str, dict[str, str | None]] = {}
        for agent_id, override in self._overrides.items():
            result[agent_id] = {
                "system_prompt": override.system_prompt,
                "prompt_prefix": override.prompt_prefix,
            }
        return result

    def has_overrides(self) -> bool:
        """Check if any overrides are currently applied."""
        return bool(self._overrides)

    def clear_overrides(self) -> None:
        """Clear all applied overrides."""
        self._overrides = {}


__all__ = [
    "AgentPromptOverride",
    "AgentId",
    "PromptOverrides",
    "PromptRegistry",
    "SUPPORTED_PROMPT_AGENTS",
]
