"""Tests for the prompt registry and override models."""

from __future__ import annotations

import pytest

from cc_deep_research.prompts import (
    SUPPORTED_PROMPT_AGENTS,
    AgentPromptOverride,
    PromptOverrides,
    PromptRegistry,
)


class TestAgentPromptOverride:
    """Tests for AgentPromptOverride model."""

    def test_empty_override(self) -> None:
        """Test that an empty override is valid."""
        override = AgentPromptOverride()
        assert override.system_prompt is None
        assert override.prompt_prefix is None

    def test_system_prompt_override(self) -> None:
        """Test system prompt override."""
        override = AgentPromptOverride(system_prompt="Custom system prompt")
        assert override.system_prompt == "Custom system prompt"
        assert override.prompt_prefix is None

    def test_prompt_prefix_override(self) -> None:
        """Test prompt prefix override."""
        override = AgentPromptOverride(prompt_prefix="Custom prefix")
        assert override.system_prompt is None
        assert override.prompt_prefix == "Custom prefix"

    def test_both_overrides(self) -> None:
        """Test both system prompt and prefix override."""
        override = AgentPromptOverride(
            system_prompt="Custom system",
            prompt_prefix="Custom prefix",
        )
        assert override.system_prompt == "Custom system"
        assert override.prompt_prefix == "Custom prefix"

    def test_whitespace_stripped_to_none(self) -> None:
        """Test that whitespace-only values are stripped to None."""
        override = AgentPromptOverride(system_prompt="   ", prompt_prefix="\n\t")
        assert override.system_prompt is None
        assert override.prompt_prefix is None

    def test_whitespace_stripped_from_valid_value(self) -> None:
        """Test that whitespace is stripped from valid values."""
        override = AgentPromptOverride(
            system_prompt="  Valid prompt  ",
            prompt_prefix="  Valid prefix  ",
        )
        assert override.system_prompt == "Valid prompt"
        assert override.prompt_prefix == "Valid prefix"


class TestPromptOverrides:
    """Tests for PromptOverrides model."""

    def test_empty_overrides(self) -> None:
        """Test empty overrides collection."""
        overrides = PromptOverrides()
        assert overrides.is_empty() is True

    def test_valid_agent_ids(self) -> None:
        """Test that valid agent IDs are accepted."""
        overrides = PromptOverrides(
            overrides={
                "analyzer": AgentPromptOverride(prompt_prefix="Test"),
                "deep_analyzer": AgentPromptOverride(system_prompt="Test"),
            }
        )
        assert overrides.is_empty() is False

    def test_invalid_agent_ids_rejected(self) -> None:
        """Test that unknown agent IDs are rejected."""
        with pytest.raises(ValueError, match="Unknown agent ids"):
            PromptOverrides(
                overrides={
                    "unknown_agent": AgentPromptOverride(prompt_prefix="Test"),
                }
            )

    def test_is_empty_with_no_values(self) -> None:
        """Test is_empty returns True when overrides have no values."""
        overrides = PromptOverrides(
            overrides={
                "analyzer": AgentPromptOverride(),
            }
        )
        assert overrides.is_empty() is True

    def test_is_empty_with_values(self) -> None:
        """Test is_empty returns False when overrides have values."""
        overrides = PromptOverrides(
            overrides={
                "analyzer": AgentPromptOverride(prompt_prefix="Test"),
            }
        )
        assert overrides.is_empty() is False


class TestPromptRegistry:
    """Tests for PromptRegistry class."""

    def test_default_registry_creation(self) -> None:
        """Test creating a registry with defaults."""
        registry = PromptRegistry()
        assert registry.has_overrides() is False

    def test_apply_overrides_from_model(self) -> None:
        """Test applying overrides from PromptOverrides model."""
        registry = PromptRegistry()
        overrides = PromptOverrides(
            overrides={
                "analyzer": AgentPromptOverride(prompt_prefix="Custom prefix"),
            }
        )
        registry.apply_overrides(overrides)
        assert registry.has_overrides() is True

    def test_apply_none_overrides(self) -> None:
        """Test applying None clears overrides."""
        registry = PromptRegistry()
        registry.apply_raw_overrides({"analyzer": {"prompt_prefix": "Test"}})
        assert registry.has_overrides() is True

        registry.apply_overrides(None)
        assert registry.has_overrides() is False

    def test_apply_raw_overrides(self) -> None:
        """Test applying raw dictionary overrides."""
        registry = PromptRegistry()
        registry.apply_raw_overrides({
            "analyzer": {"prompt_prefix": "Custom prefix"},
        })
        assert registry.has_overrides() is True

    def test_apply_raw_overrides_ignores_unknown_agents(self) -> None:
        """Test that unknown agent IDs are ignored in raw overrides."""
        registry = PromptRegistry()
        registry.apply_raw_overrides({
            "unknown_agent": {"prompt_prefix": "Test"},
            "analyzer": {"prompt_prefix": "Valid"},
        })
        effective = registry.get_effective_overrides()
        assert "unknown_agent" not in effective
        assert "analyzer" in effective

    def test_apply_raw_overrides_strips_whitespace(self) -> None:
        """Test that whitespace-only values are ignored."""
        registry = PromptRegistry()
        registry.apply_raw_overrides({
            "analyzer": {"prompt_prefix": "   "},
        })
        assert registry.has_overrides() is False

    def test_resolve_prompt_default(self) -> None:
        """Test resolving prompt with no overrides."""
        registry = PromptRegistry()
        system_prompt, prompt_prefix, used_override = registry.resolve_prompt(
            "analyzer", "extract_themes"
        )
        assert used_override is False
        assert prompt_prefix is None

    def test_resolve_prompt_with_prefix(self) -> None:
        """Test resolving prompt with prefix override."""
        registry = PromptRegistry()
        registry.apply_raw_overrides({
            "analyzer": {"prompt_prefix": "Custom prefix"},
        })
        system_prompt, prompt_prefix, used_override = registry.resolve_prompt(
            "analyzer", "extract_themes"
        )
        assert used_override is True
        assert prompt_prefix == "Custom prefix"

    def test_get_effective_overrides(self) -> None:
        """Test getting effective overrides."""
        registry = PromptRegistry()
        registry.apply_raw_overrides({
            "analyzer": {"prompt_prefix": "Prefix 1"},
            "deep_analyzer": {"system_prompt": "System 2"},
        })
        effective = registry.get_effective_overrides()
        assert "analyzer" in effective
        assert effective["analyzer"]["prompt_prefix"] == "Prefix 1"
        assert "deep_analyzer" in effective
        assert effective["deep_analyzer"]["system_prompt"] == "System 2"

    def test_clear_overrides(self) -> None:
        """Test clearing all overrides."""
        registry = PromptRegistry()
        registry.apply_raw_overrides({"analyzer": {"prompt_prefix": "Test"}})
        assert registry.has_overrides() is True

        registry.clear_overrides()
        assert registry.has_overrides() is False

    def test_custom_system_prompts(self) -> None:
        """Test registry with custom default system prompts."""
        registry = PromptRegistry(
            system_prompts={"analyzer": "Custom default system"}
        )
        system_prompt, prompt_prefix, used_override = registry.resolve_prompt(
            "analyzer", "extract_themes"
        )
        assert system_prompt == "Custom default system"

    def test_get_operation_prompt_not_implemented(self) -> None:
        """Test that get_operation_prompt is not in the core registry (handled by agents)."""
        registry = PromptRegistry()
        # The PromptRegistry doesn't have get_operation_prompt - that's handled by
        # the agent-specific code that uses the registry
        assert not hasattr(registry, "get_operation_prompt")


class TestSupportedAgents:
    """Tests for supported agent IDs."""

    def test_supported_agents_contains_expected(self) -> None:
        """Test that supported agents includes expected values."""
        assert "analyzer" in SUPPORTED_PROMPT_AGENTS
        assert "deep_analyzer" in SUPPORTED_PROMPT_AGENTS
        assert "report_quality_evaluator" in SUPPORTED_PROMPT_AGENTS

    def test_heuristic_agents_not_supported(self) -> None:
        """Test that heuristic-only agents are not in supported set."""
        assert "lead" not in SUPPORTED_PROMPT_AGENTS
        assert "expander" not in SUPPORTED_PROMPT_AGENTS
        assert "validator" not in SUPPORTED_PROMPT_AGENTS
