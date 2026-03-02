"""Configuration management for CC Deep Research CLI."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from cc_deep_research.models import ResearchDepth, SearchMode


class SearchConfig(BaseModel):
    """Search-related configuration."""

    providers: list[str] = Field(default=["tavily", "claude"])
    mode: SearchMode = Field(default=SearchMode.HYBRID_PARALLEL)
    depth: ResearchDepth = Field(default=ResearchDepth.DEEP)


class TavilyConfig(BaseModel):
    """Tavily-specific configuration."""

    api_keys: list[str] = Field(default_factory=list)
    rate_limit: int = Field(default=1000, ge=1)
    max_results: int = Field(default=100, ge=1, le=100)


class ClaudeConfig(BaseModel):
    """Claude-specific configuration."""

    max_results: int = Field(default=50, ge=1, le=100)


class MinSourcesConfig(BaseModel):
    """Minimum sources configuration per depth mode."""

    quick: int = Field(default=3, ge=1)
    standard: int = Field(default=10, ge=1)
    deep: int = Field(default=20, ge=1)


class ResearchConfig(BaseModel):
    """Research-related configuration."""

    default_depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    min_sources: MinSourcesConfig = Field(default_factory=MinSourcesConfig)
    enable_iterative_search: bool = Field(default=True)
    max_iterations: int = Field(default=3, ge=1)
    enable_cross_ref: bool = Field(default=True)
    enable_quality_scoring: bool = Field(default=True)


class OutputConfig(BaseModel):
    """Output-related configuration."""

    format: str = Field(default="markdown")
    auto_save: bool = Field(default=True)
    save_dir: str = Field(default="./reports")
    include_metadata: bool = Field(default=True)
    include_cross_ref_analysis: bool = Field(default=True)

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate output format."""
        allowed = {"markdown", "json", "html"}
        if v.lower() not in allowed:
            raise ValueError(f"format must be one of {allowed}")
        return v.lower()


class DisplayConfig(BaseModel):
    """Display-related configuration."""

    color: str = Field(default="auto")
    progress: str = Field(default="auto")
    verbose: bool = Field(default=False)

    @field_validator("color", "progress")
    @classmethod
    def validate_auto_never_always(cls, v: str) -> str:
        """Validate auto/never/always fields."""
        allowed = {"always", "auto", "never"}
        if v.lower() not in allowed:
            raise ValueError(f"must be one of {allowed}")
        return v.lower()


class Config(BaseModel):
    """Main configuration model."""

    search: SearchConfig = Field(default_factory=SearchConfig)
    tavily: TavilyConfig = Field(default_factory=TavilyConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Environment variable overrides
    tavily_api_keys: list[str] = Field(default_factory=list, alias="TAVILY_API_KEYS")
    config_path: Path | None = Field(default=None, alias="CC_DEEP_RESEARCH_CONFIG")
    depth: ResearchDepth | None = Field(default=None, alias="CC_DEEP_RESEARCH_DEPTH")
    output_format: str | None = Field(default=None, alias="CC_DEEP_RESEARCH_FORMAT")
    no_color: bool = Field(default=False, alias="NO_COLOR")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "cc-deep-research" / "config.yaml"
    return Path.home() / ".config" / "cc-deep-research" / "config.yaml"


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file and environment variables.

    Args:
        config_path: Optional path to config file. If not provided,
                     uses default location.

    Returns:
        Config object with merged settings.
    """
    settings = Settings()

    # Determine config path
    if config_path is None:
        config_path = settings.config_path or get_default_config_path()

    # Load from file if exists
    config_data: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}

    # Create config from file data
    config = Config(**config_data)

    # Apply environment variable overrides
    if settings.tavily_api_keys:
        config.tavily.api_keys = settings.tavily_api_keys

    if settings.depth:
        config.search.depth = settings.depth
        config.research.default_depth = settings.depth

    if settings.output_format:
        config.output.format = settings.output_format

    if settings.no_color:
        config.display.color = "never"

    return config


def save_config(config: Config, config_path: Path | None = None) -> None:
    """Save configuration to file.

    Args:
        config: Config object to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    if config_path is None:
        config_path = get_default_config_path()

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict and save
    config_data = config.model_dump(mode="python")

    with open(config_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)


def get_default_config() -> Config:
    """Get a default configuration.

    Returns:
        Config object with default values.
    """
    return Config()


def create_default_config_file(config_path: Path | None = None) -> Path:
    """Create a default configuration file.

    Args:
        config_path: Optional path for config file.

    Returns:
        Path to the created config file.
    """
    if config_path is None:
        config_path = get_default_config_path()

    config = get_default_config()
    save_config(config, config_path)

    return config_path


__all__ = [
    "Config",
    "SearchConfig",
    "TavilyConfig",
    "ClaudeConfig",
    "ResearchConfig",
    "OutputConfig",
    "DisplayConfig",
    "MinSourcesConfig",
    "Settings",
    "load_config",
    "save_config",
    "get_default_config",
    "get_default_config_path",
    "create_default_config_file",
]
