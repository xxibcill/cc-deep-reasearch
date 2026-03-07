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

    providers: list[str] = Field(default=["tavily"])
    mode: SearchMode = Field(default=SearchMode.TAVILY_PRIMARY)
    depth: ResearchDepth = Field(default=ResearchDepth.DEEP)

    @field_validator("providers")
    @classmethod
    def normalize_provider_names(cls, values: list[str]) -> list[str]:
        """Normalize provider names while preserving first-seen order."""
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values or ["tavily"]:
            provider_name = value.strip().lower()
            if not provider_name or provider_name in seen:
                continue
            seen.add(provider_name)
            normalized.append(provider_name)
        return normalized or ["tavily"]


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
    deep: int = Field(default=50, ge=1)


class ResearchConfig(BaseModel):
    """Research-related configuration."""

    default_depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    min_sources: MinSourcesConfig = Field(default_factory=MinSourcesConfig)
    enable_iterative_search: bool = Field(default=True)
    max_iterations: int = Field(default=3, ge=1)
    enable_cross_ref: bool = Field(default=True)
    enable_quality_scoring: bool = Field(default=True)
    deep_analysis_passes: int = Field(default=3, ge=1, le=5)
    deep_analysis_tokens: int = Field(default=150000, ge=100000, le=300000)

    # Content fetching configuration
    top_sources_for_content: int = Field(default=15, ge=5, le=30)

    # Content quality configuration
    content_min_quality_threshold: int = Field(default=100, ge=50, le=500)
    enable_content_cleaning: bool = Field(default=True)

    # AI analysis configuration
    ai_analysis_enabled: bool = Field(default=True)
    ai_num_themes: int = Field(default=8, ge=3, le=15)
    ai_deep_num_themes: int = Field(default=12, ge=5, le=20)
    max_sources_per_theme: int = Field(default=5, ge=2, le=10)
    ai_integration_method: str = Field(
        default="hybrid",
        description="Method for AI integration: 'heuristic', 'agent', 'api', 'hybrid'"
    )
    ai_temperature: float = Field(default=0.3, ge=0.0, le=1.0)


class OutputConfig(BaseModel):
    """Output-related configuration."""

    format: str = Field(default="markdown")
    auto_save: bool = Field(default=True)
    save_dir: str = Field(default="./reports")
    include_metadata: bool = Field(default=True)
    include_cross_ref_analysis: bool = Field(default=True)
    pdf_enabled: bool = Field(default=False)
    pdf_css_template: str | None = Field(default=None)

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


class AgentConfig(BaseModel):
    """Individual agent configuration."""

    model: str = Field(default="claude-sonnet-4-6")
    max_turns: int = Field(default=10, ge=1, le=50)
    mode: str = Field(default="default")  # default, bypassPermissions, dontAsk


class AgentTeamConfig(BaseModel):
    """Agent team configuration."""

    enabled: bool = Field(default=True)
    team_size: int = Field(default=4, ge=2, le=8)
    parallel_execution: bool = Field(default=True)
    timeout_seconds: int = Field(default=300, ge=30, le=600)
    fallback_to_sequential: bool = Field(default=True)

    # Parallel execution configuration
    num_researchers: int = Field(default=3, ge=1, le=8)
    researcher_timeout: int = Field(default=120, ge=30, le=300)
    enable_reflection: bool = Field(default=True)
    max_reflection_points: int = Field(default=5, ge=1, le=10)


class Config(BaseModel):
    """Main configuration model."""

    search: SearchConfig = Field(default_factory=SearchConfig)
    tavily: TavilyConfig = Field(default_factory=TavilyConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    research_agent: AgentConfig = Field(default_factory=AgentConfig)
    search_team: AgentTeamConfig = Field(default_factory=AgentTeamConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Environment variable overrides (not including TAVILY_API_KEYS - handled separately)
    config_path: Path | None = Field(default=None, alias="CC_DEEP_RESEARCH_CONFIG")
    depth: ResearchDepth | None = Field(default=None, alias="CC_DEEP_RESEARCH_DEPTH")
    output_format: str | None = Field(default=None, alias="CC_DEEP_RESEARCH_FORMAT")
    no_color: bool = Field(default=False, alias="NO_COLOR")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
        "env_prefix": "",
    }


def _parse_api_keys_from_env() -> list[str]:
    """Parse TAVILY_API_KEYS from environment variable.

    Returns:
        List of API keys from comma-separated env var.
    """
    env_value = os.environ.get("TAVILY_API_KEYS", "")
    if not env_value:
        return []
    return [k.strip() for k in env_value.split(",") if k.strip()]


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
    api_keys = _parse_api_keys_from_env()
    if api_keys:
        config.tavily.api_keys = api_keys

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

    # Convert to dict and save (use json mode to serialize enums as strings)
    config_data = config.model_dump(mode="json")

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
    "AgentConfig",
    "AgentTeamConfig",
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
