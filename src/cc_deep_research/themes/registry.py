"""Theme registry for loading and managing workflow configurations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import ResearchTheme, WorkflowConfig
from .presets import BUILTIN_PRESETS, get_preset


class ThemeRegistry:
    """Registry for managing research theme configurations.

    Supports loading built-in presets and custom theme configurations
    from YAML files.
    """

    def __init__(
        self,
        *,
        custom_themes_dir: Path | None = None,
    ) -> None:
        """Initialize the theme registry.

        Args:
            custom_themes_dir: Optional directory containing custom theme configs.
        """
        self._custom_themes_dir = custom_themes_dir
        self._custom_themes: dict[ResearchTheme, WorkflowConfig] = {}
        self._loaded_custom = False

    def _ensure_custom_loaded(self) -> None:
        """Load custom themes from directory if not already loaded."""
        if self._loaded_custom or self._custom_themes_dir is None:
            return

        self._load_custom_themes(self._custom_themes_dir)
        self._loaded_custom = True

    def _load_custom_themes(self, themes_dir: Path) -> None:
        """Load custom theme configurations from a directory.

        Args:
            themes_dir: Directory containing YAML theme config files.
        """
        if not themes_dir.exists():
            return

        for config_file in themes_dir.glob("*.yaml"):
            try:
                self._load_theme_from_file(config_file)
            except Exception:
                # Log warning but don't fail - custom themes are optional
                pass

    def _load_theme_from_file(self, config_file: Path) -> None:
        """Load a single theme configuration from a YAML file.

        Args:
            config_file: Path to the YAML config file.
        """
        content = config_file.read_text()
        data = yaml.safe_load(content)

        if not data or "theme" not in data:
            return

        theme_str = data.get("theme")
        try:
            theme = ResearchTheme(theme_str)
        except ValueError:
            # Unknown theme - could be a custom theme identifier
            return

        config = self._parse_theme_config(theme, data)
        if config:
            self._custom_themes[theme] = config

    def _parse_theme_config(
        self,
        theme: ResearchTheme,
        data: dict[str, Any],
    ) -> WorkflowConfig | None:
        """Parse a theme configuration from dictionary data.

        Args:
            theme: The theme enum value.
            data: The raw configuration data.

        Returns:
            Parsed WorkflowConfig or None if invalid.
        """
        try:
            return WorkflowConfig(
                theme=theme,
                display_name=data.get("display_name", theme.value),
                description=data.get("description", ""),
                phases=data.get(
                    "phases",
                    ["strategy", "expand", "collect", "analyze", "validate", "report"],
                ),
                source_requirements=data.get("source_requirements", {}),
                output_template=data.get("output_template"),
                skip_deep_analysis=data.get("skip_deep_analysis", False),
                skip_validation=data.get("skip_validation", False),
                enable_iterative_search=data.get("enable_iterative_search"),
            )
        except Exception:
            return None

    def get_config(self, theme: ResearchTheme) -> WorkflowConfig:
        """Get the workflow configuration for a theme.

        Custom themes take precedence over built-in presets.

        Args:
            theme: The theme to get configuration for.

        Returns:
            The workflow configuration for the theme.

        Raises:
            KeyError: If the theme is not found.
        """
        self._ensure_custom_loaded()

        # Check custom themes first
        if theme in self._custom_themes:
            return self._custom_themes[theme]

        # Fall back to built-in presets
        preset = get_preset(theme)
        if preset is not None:
            return preset

        raise KeyError(f"Theme not found: {theme}")

    def has_theme(self, theme: ResearchTheme) -> bool:
        """Check if a theme is registered.

        Args:
            theme: The theme to check.

        Returns:
            True if the theme is registered.
        """
        self._ensure_custom_loaded()
        return theme in self._custom_themes or theme in BUILTIN_PRESETS

    def list_themes(self) -> list[ResearchTheme]:
        """List all registered themes.

        Returns:
            List of registered theme enum values.
        """
        self._ensure_custom_loaded()
        all_themes = set(self._custom_themes.keys()) | set(BUILTIN_PRESETS.keys())
        return sorted(all_themes, key=lambda t: t.value)

    def list_theme_info(self) -> list[dict[str, str]]:
        """List all themes with their metadata.

        Returns:
            List of dictionaries with theme info.
        """
        self._ensure_custom_loaded()
        result = []

        # Start with built-in themes
        seen = set()
        for config in BUILTIN_PRESETS.values():
            seen.add(config.theme)
            result.append({
                "theme": config.theme.value,
                "display_name": config.display_name,
                "description": config.description,
                "source": "builtin",
            })

        # Add custom themes (may override built-in)
        for theme, config in self._custom_themes.items():
            if theme in seen:
                # Replace built-in with custom
                result = [r for r in result if r["theme"] != theme.value]
            result.append({
                "theme": config.theme.value,
                "display_name": config.display_name,
                "description": config.description,
                "source": "custom",
            })

        return sorted(result, key=lambda x: x["theme"])

    def register_theme(self, config: WorkflowConfig) -> None:
        """Register a custom theme configuration.

        Args:
            config: The workflow configuration to register.
        """
        self._custom_themes[config.theme] = config

    def unregister_theme(self, theme: ResearchTheme) -> bool:
        """Unregister a custom theme.

        Note: Built-in themes cannot be unregistered.

        Args:
            theme: The theme to unregister.

        Returns:
            True if the theme was unregistered.
        """
        if theme in self._custom_themes:
            del self._custom_themes[theme]
            return True
        return False

    def reload_custom_themes(self) -> int:
        """Reload custom themes from the configured directory.

        Returns:
            Number of custom themes loaded.
        """
        self._custom_themes.clear()
        self._loaded_custom = False
        self._ensure_custom_loaded()
        return len(self._custom_themes)


# Global registry instance
_global_registry: ThemeRegistry | None = None


def get_theme_registry(
    *,
    custom_themes_dir: Path | None = None,
    refresh: bool = False,
) -> ThemeRegistry:
    """Get the global theme registry instance.

    Args:
        custom_themes_dir: Optional directory for custom themes.
        refresh: Force creation of a new registry.

    Returns:
        The global ThemeRegistry instance.
    """
    global _global_registry

    if _global_registry is None or refresh:
        _global_registry = ThemeRegistry(custom_themes_dir=custom_themes_dir)

    return _global_registry


__all__ = [
    "ThemeRegistry",
    "get_theme_registry",
]
