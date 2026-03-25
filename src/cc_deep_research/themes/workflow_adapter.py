"""Theme workflow adapter for configuring orchestrator based on theme."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.prompts import PromptRegistry

from .models import ResearchTheme, WorkflowConfig
from .registry import ThemeRegistry


class ThemeWorkflowAdapter:
    """Adapts orchestrator configuration based on research theme.

    This class bridges the theme system with the orchestrator,
    applying theme-specific configurations to the research workflow.
    """

    def __init__(
        self,
        *,
        registry: ThemeRegistry | None = None,
    ) -> None:
        """Initialize the workflow adapter.

        Args:
            registry: Optional theme registry. Uses global registry if not provided.
        """
        self._registry = registry or ThemeRegistry()

    def get_workflow_config(self, theme: ResearchTheme) -> WorkflowConfig:
        """Get the workflow configuration for a theme.

        Args:
            theme: The research theme.

        Returns:
            The workflow configuration.
        """
        return self._registry.get_config(theme)

    def apply_to_config(
        self,
        base_config: Config,
        workflow_config: WorkflowConfig,
    ) -> Config:
        """Apply theme configuration to a base config.

        Args:
            base_config: The base configuration to modify.
            workflow_config: The theme workflow configuration.

        Returns:
            Modified configuration (copy).
        """
        config = base_config.model_copy(deep=True)

        # Apply iterative search override
        if workflow_config.enable_iterative_search is not None:
            config.research.enable_iterative_search = workflow_config.enable_iterative_search

        return config

    def apply_to_prompt_registry(
        self,
        prompt_registry: PromptRegistry,
        workflow_config: WorkflowConfig,
    ) -> PromptRegistry:
        """Apply theme-specific prompt overrides.

        Args:
            prompt_registry: The base prompt registry to modify.
            workflow_config: The theme workflow configuration.

        Returns:
            Modified prompt registry.
        """
        # Get theme-specific prompt overrides
        from .prompts import get_theme_prompt_overrides

        overrides = get_theme_prompt_overrides(workflow_config.theme)
        if overrides:
            prompt_registry.apply_raw_overrides(overrides)

        return prompt_registry

    def get_phase_hooks(
        self,
        workflow_config: WorkflowConfig,
    ) -> dict[str, dict[str, Any]]:
        """Get phase-specific hook configurations.

        Args:
            workflow_config: The theme workflow configuration.

        Returns:
            Dictionary mapping phase names to hook configurations.
        """
        hooks: dict[str, dict[str, Any]] = {}

        for phase_name, phase_config in workflow_config.phase_configs.items():
            if phase_config.enabled:
                hooks[phase_name] = {
                    "weight": phase_config.weight,
                    **phase_config.additional_params,
                }

        return hooks

    def get_enabled_phases(self, workflow_config: WorkflowConfig) -> list[str]:
        """Get the list of enabled phases for a workflow.

        Args:
            workflow_config: The theme workflow configuration.

        Returns:
            List of enabled phase names in order.
        """
        return [
            phase
            for phase in workflow_config.phases
            if workflow_config.is_phase_enabled(phase)
        ]

    def get_source_requirements(
        self,
        workflow_config: WorkflowConfig,
    ) -> dict[str, Any]:
        """Get source collection requirements for a workflow.

        Args:
            workflow_config: The theme workflow configuration.

        Returns:
            Dictionary of source requirements.
        """
        reqs = workflow_config.source_requirements
        return {
            "min_sources": reqs.min_sources,
            "preferred_source_types": reqs.preferred_source_types,
            "prioritize_official_sources": reqs.prioritize_official_sources,
            "credibility_threshold": reqs.credibility_threshold,
        }

    def get_output_template(self, workflow_config: WorkflowConfig) -> str | None:
        """Get the output template for a workflow.

        Args:
            workflow_config: The theme workflow configuration.

        Returns:
            Output template name or None.
        """
        return workflow_config.output_template

    def should_skip_phase(
        self,
        workflow_config: WorkflowConfig,
        phase_name: str,
    ) -> bool:
        """Check if a phase should be skipped for a workflow.

        Args:
            workflow_config: The theme workflow configuration.
            phase_name: Name of the phase to check.

        Returns:
            True if the phase should be skipped.
        """
        # Check explicit skip flags
        if phase_name == "deep_analysis" and workflow_config.skip_deep_analysis:
            return True
        if phase_name == "validate" and workflow_config.skip_validation:
            return True

        # Check phase config
        return not workflow_config.is_phase_enabled(phase_name)

    def get_theme_summary(self, theme: ResearchTheme) -> dict[str, Any]:
        """Get a summary of theme configuration for display.

        Args:
            theme: The research theme.

        Returns:
            Dictionary with theme summary information.
        """
        config = self.get_workflow_config(theme)
        return {
            "theme": config.theme.value,
            "display_name": config.display_name,
            "description": config.description,
            "phases": self.get_enabled_phases(config),
            "min_sources": config.source_requirements.min_sources,
            "skip_deep_analysis": config.skip_deep_analysis,
            "skip_validation": config.skip_validation,
        }


__all__ = ["ThemeWorkflowAdapter"]
