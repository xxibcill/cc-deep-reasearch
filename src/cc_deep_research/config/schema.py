"""Configuration schema models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from cc_deep_research.models.search import ResearchDepth
from cc_deep_research.models.support import SearchMode


def _normalize_api_key_list(*values: str | list[str] | None) -> list[str]:
    """Normalize API keys while preserving first-seen order."""
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if candidate is None:
                continue
            key = candidate.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(key)

    return normalized


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


class SearchCacheConfig(BaseModel):
    """Persistent web search cache configuration."""

    enabled: bool = Field(default=False)
    ttl_seconds: int = Field(default=3600, ge=1)
    max_entries: int = Field(default=1000, ge=1)
    db_path: str | None = Field(default=None)

    def resolve_db_path(self, config_path: Path | None = None) -> Path:
        """Return the configured cache database path or a stable default."""
        if self.db_path:
            return Path(self.db_path).expanduser()
        if config_path is not None:
            return config_path.expanduser().with_name("search-cache.sqlite3")
        return Path.cwd() / "search-cache.sqlite3"


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


class ResearchQualitySettings(BaseSettings):
    """Quality control settings for research output."""

    strict_depth_limits: bool = Field(default=True)
    enforce_quick_mode_limit: bool = Field(default=True)
    enable_truncation_detection: bool = Field(default=True)
    enable_protocol_filtering: bool = Field(default=True)
    max_protocol_ratio: float = Field(default=0.3)
    min_primary_source_ratio: float = Field(default=0.3)
    enable_source_type_classification: bool = Field(default=True)
    enable_auto_gap_detection: bool = Field(default=True)
    max_follow_up_iterations: int = Field(default=2)
    enable_post_validation: bool = Field(default=True)
    fail_on_validation_errors: bool = Field(default=False)
    enable_report_quality_evaluation: bool = Field(default=True)
    min_report_quality_score: float = Field(default=0.6, ge=0.0, le=1.0)
    enable_report_refinement: bool = Field(default=True)


class ResearchConfig(BaseModel):
    """Research-related configuration."""

    default_depth: ResearchDepth = Field(default=ResearchDepth.DEEP)
    min_sources: MinSourcesConfig = Field(default_factory=MinSourcesConfig)
    enable_iterative_search: bool = Field(default=True)
    max_iterations: int = Field(default=3, ge=1)
    quality: ResearchQualitySettings = Field(default_factory=ResearchQualitySettings)
    enable_cross_ref: bool = Field(default=True)
    enable_quality_scoring: bool = Field(default=True)
    deep_analysis_passes: int = Field(default=3, ge=1, le=5)
    deep_analysis_tokens: int = Field(default=150000, ge=100000, le=300000)
    top_sources_for_content: int = Field(default=15, ge=5, le=30)
    content_min_quality_threshold: int = Field(default=100, ge=50, le=500)
    enable_content_cleaning: bool = Field(default=True)
    ai_analysis_enabled: bool = Field(default=True)
    ai_num_themes: int = Field(default=8, ge=3, le=15)
    ai_deep_num_themes: int = Field(default=12, ge=5, le=20)
    max_sources_per_theme: int = Field(default=5, ge=2, le=10)
    ai_integration_method: str = Field(
        default="hybrid",
        description="Method for AI integration: 'heuristic', 'agent', 'api', 'hybrid'",
    )
    ai_temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    claude_cli_path: str | None = Field(
        default=None,
        description="Optional path override for the Claude Code CLI executable",
    )
    claude_cli_timeout_seconds: int = Field(default=180, ge=30, le=900)


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
    def validate_format(cls, value: str) -> str:
        """Validate output format."""
        allowed = {"markdown", "json", "html"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"format must be one of {allowed}")
        return normalized


class DisplayConfig(BaseModel):
    """Display-related configuration."""

    color: str = Field(default="auto")
    progress: str = Field(default="auto")
    verbose: bool = Field(default=False)

    @field_validator("color", "progress")
    @classmethod
    def validate_auto_never_always(cls, value: str) -> str:
        """Validate auto/never/always fields."""
        allowed = {"always", "auto", "never"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"must be one of {allowed}")
        return normalized


class AgentConfig(BaseModel):
    """Individual agent configuration."""

    model: str = Field(default="claude-sonnet-4-6")
    max_turns: int = Field(default=10, ge=1, le=50)
    mode: str = Field(default="default")


class AgentTeamConfig(BaseModel):
    """Agent team configuration."""

    enabled: bool = Field(default=True)
    team_size: int = Field(default=4, ge=2, le=8)
    parallel_execution: bool = Field(default=True)
    timeout_seconds: int = Field(default=300, ge=30, le=600)
    fallback_to_sequential: bool = Field(default=True)
    num_researchers: int = Field(default=3, ge=1, le=8)
    researcher_timeout: int = Field(default=120, ge=30, le=300)
    enable_reflection: bool = Field(default=True)
    max_reflection_points: int = Field(default=5, ge=1, le=10)


class LLMClaudeCLIConfig(BaseModel):
    """Claude CLI transport configuration."""

    enabled: bool = Field(default=True)
    path: str | None = Field(
        default=None,
        description="Optional path override for the Claude Code CLI executable",
    )
    timeout_seconds: int = Field(default=180, ge=30, le=900)
    model: str = Field(default="claude-sonnet-4-6")


class LLMOpenRouterConfig(BaseModel):
    """OpenRouter API transport configuration."""

    enabled: bool = Field(default=False)
    api_key: str | None = Field(default=None)
    api_keys: list[str] = Field(default_factory=list)
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    timeout_seconds: int = Field(default=120, ge=30, le=600)
    model: str = Field(default="anthropic/claude-sonnet-4")
    extra_headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("api_keys")
    @classmethod
    def normalize_api_keys(cls, values: list[str]) -> list[str]:
        """Normalize configured OpenRouter API keys."""
        return _normalize_api_key_list(values)

    def get_api_keys(self) -> list[str]:
        """Return the configured OpenRouter keys in priority order."""
        return _normalize_api_key_list(self.api_key, self.api_keys)


class LLMCerebrasConfig(BaseModel):
    """Cerebras API transport configuration."""

    enabled: bool = Field(default=False)
    api_key: str | None = Field(default=None)
    api_keys: list[str] = Field(default_factory=list)
    base_url: str = Field(default="https://api.cerebras.ai/v1")
    timeout_seconds: int = Field(default=60, ge=10, le=300)
    model: str = Field(default="llama-3.3-70b")

    @field_validator("api_keys")
    @classmethod
    def normalize_api_keys(cls, values: list[str]) -> list[str]:
        """Normalize configured Cerebras API keys."""
        return _normalize_api_key_list(values)

    def get_api_keys(self) -> list[str]:
        """Return the configured Cerebras keys in priority order."""
        return _normalize_api_key_list(self.api_key, self.api_keys)


class LLMAnthropicConfig(BaseModel):
    """Anthropic API transport configuration."""

    enabled: bool = Field(default=False)
    api_key: str | None = Field(default=None)
    api_keys: list[str] = Field(default_factory=list)
    base_url: str = Field(default="https://api.anthropic.com")
    timeout_seconds: int = Field(default=120, ge=10, le=600)
    model: str = Field(default="claude-sonnet-4-6")
    max_tokens: int = Field(default=512, ge=1, le=128000)

    @field_validator("api_keys")
    @classmethod
    def normalize_api_keys(cls, values: list[str]) -> list[str]:
        """Normalize configured Anthropic API keys."""
        return _normalize_api_key_list(values)

    def get_api_keys(self) -> list[str]:
        """Return the configured Anthropic keys in priority order."""
        return _normalize_api_key_list(self.api_key, self.api_keys)


class LLMRouteDefaults(BaseModel):
    """Default route assignments for agents."""

    analyzer: str = Field(default="claude_cli")
    deep_analyzer: str = Field(default="claude_cli")
    report_quality_evaluator: str = Field(default="claude_cli")
    reporter: str = Field(default="claude_cli")
    default: str = Field(default="claude_cli")


class LLMConfig(BaseModel):
    """LLM routing configuration."""

    claude_cli: LLMClaudeCLIConfig = Field(default_factory=LLMClaudeCLIConfig)
    openrouter: LLMOpenRouterConfig = Field(default_factory=LLMOpenRouterConfig)
    cerebras: LLMCerebrasConfig = Field(default_factory=LLMCerebrasConfig)
    anthropic: LLMAnthropicConfig = Field(default_factory=LLMAnthropicConfig)
    route_defaults: LLMRouteDefaults = Field(default_factory=LLMRouteDefaults)
    fallback_order: list[str] = Field(
        default_factory=lambda: ["claude_cli", "openrouter", "cerebras", "anthropic", "heuristic"]
    )

    def get_enabled_transports(self) -> list[str]:
        """Get list of enabled transport names in fallback order."""
        transports: list[str] = []
        for name in self.fallback_order:
            is_enabled = (
                (name == "claude_cli" and self.claude_cli.enabled)
                or (
                    name == "openrouter"
                    and self.openrouter.enabled
                    and self.openrouter.get_api_keys()
                )
                or (
                    name == "cerebras"
                    and self.cerebras.enabled
                    and self.cerebras.get_api_keys()
                )
                or (
                    name == "anthropic"
                    and self.anthropic.enabled
                    and self.anthropic.get_api_keys()
                )
                or name == "heuristic"
            )
            if is_enabled:
                transports.append(name)
        return transports

    def get_route_for_agent(self, agent_id: str) -> str:
        """Get the default route for an agent."""
        route_map = {
            "analyzer": self.route_defaults.analyzer,
            "deep_analyzer": self.route_defaults.deep_analyzer,
            "report_quality_evaluator": self.route_defaults.report_quality_evaluator,
            "reporter": self.route_defaults.reporter,
        }
        return route_map.get(agent_id, self.route_defaults.default)


class Config(BaseModel):
    """Main configuration model."""

    search: SearchConfig = Field(default_factory=SearchConfig)
    search_cache: SearchCacheConfig = Field(default_factory=SearchCacheConfig)
    tavily: TavilyConfig = Field(default_factory=TavilyConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    research_agent: AgentConfig = Field(default_factory=AgentConfig)
    search_team: AgentTeamConfig = Field(default_factory=AgentTeamConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


class DashboardConfig(BaseModel):
    """Dashboard configuration for real-time monitoring."""

    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=8000)


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    config_path: Path | None = Field(default=None, alias="CC_DEEP_RESEARCH_CONFIG")
    depth: ResearchDepth | None = Field(default=None, alias="CC_DEEP_RESEARCH_DEPTH")
    output_format: str | None = Field(default=None, alias="CC_DEEP_RESEARCH_FORMAT")
    no_color: bool = Field(default=False, alias="NO_COLOR")
    dashboard_enabled: bool = Field(default=False, alias="DASHBOARD_ENABLED")
    dashboard_host: str | None = Field(default=None, alias="DASHBOARD_HOST")
    dashboard_port: int | None = Field(default=None, alias="DASHBOARD_PORT")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
        "env_prefix": "",
    }


__all__ = [
    "AgentConfig",
    "AgentTeamConfig",
    "ClaudeConfig",
    "Config",
    "DashboardConfig",
    "DisplayConfig",
    "LLMAnthropicConfig",
    "LLMCerebrasConfig",
    "LLMClaudeCLIConfig",
    "LLMConfig",
    "LLMOpenRouterConfig",
    "LLMRouteDefaults",
    "MinSourcesConfig",
    "OutputConfig",
    "ResearchConfig",
    "ResearchQualitySettings",
    "SearchConfig",
    "SearchCacheConfig",
    "Settings",
    "TavilyConfig",
    "_normalize_api_key_list",
]
