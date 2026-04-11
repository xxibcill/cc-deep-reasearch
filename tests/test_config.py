"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from cc_deep_research.config import (
    Config,
    ConfigOverrideError,
    ConfigPatchError,
    DisplayConfig,
    LLMAnthropicConfig,
    LLMCerebrasConfig,
    LLMConfig,
    LLMOpenRouterConfig,
    LLMRouteDefaults,
    OutputConfig,
    ResearchConfig,
    SearchCacheConfig,
    SearchConfig,
    Settings,
    TavilyConfig,
    _parse_api_keys_from_env,
    build_config_response,
    create_default_config_file,
    get_default_config_path,
    load_config,
    save_config,
    update_config,
)
from cc_deep_research.models import ResearchDepth, SearchMode
from cc_deep_research.research_runs import (
    ResearchRunRequest,
    apply_research_request_config_overrides,
)


class TestSearchConfig:
    """Tests for SearchConfig model."""

    def test_default_search_config(self) -> None:
        """Test default SearchConfig values."""
        config = SearchConfig()
        assert config.providers == ["tavily"]
        assert config.mode == SearchMode.TAVILY_PRIMARY
        assert config.depth == ResearchDepth.DEEP

    def test_custom_search_config(self) -> None:
        """Test custom SearchConfig values."""
        config = SearchConfig(
            providers=["tavily"],
            mode=SearchMode.TAVILY_PRIMARY,
            depth=ResearchDepth.QUICK,
        )
        assert config.providers == ["tavily"]
        assert config.mode == SearchMode.TAVILY_PRIMARY
        assert config.depth == ResearchDepth.QUICK

    def test_provider_names_are_normalized_and_deduplicated(self) -> None:
        """Provider names should be normalized for explicit config selection."""
        config = SearchConfig(providers=[" Tavily ", "tavily_basic", "TAVILY"])

        assert config.providers == ["tavily", "tavily_basic"]


class TestTavilyConfig:
    """Tests for TavilyConfig model."""

    def test_default_tavily_config(self) -> None:
        """Test default TavilyConfig values."""
        config = TavilyConfig()
        assert config.api_keys == []
        assert config.rate_limit == 1000
        assert config.max_results == 100

    def test_custom_tavily_config(self) -> None:
        """Test custom TavilyConfig values."""
        config = TavilyConfig(
            api_keys=["key1", "key2"],
            rate_limit=500,
            max_results=50,
        )
        assert config.api_keys == ["key1", "key2"]
        assert config.rate_limit == 500
        assert config.max_results == 50

    def test_rate_limit_validation(self) -> None:
        """Test rate_limit must be positive."""
        with pytest.raises(ValueError):
            TavilyConfig(rate_limit=0)
        with pytest.raises(ValueError):
            TavilyConfig(rate_limit=-1)


class TestResearchConfig:
    """Tests for ResearchConfig model."""

    def test_default_research_config(self) -> None:
        """Test default ResearchConfig values."""
        config = ResearchConfig()
        assert config.default_depth == ResearchDepth.DEEP
        assert config.min_sources.quick == 3
        assert config.min_sources.standard == 10
        assert config.min_sources.deep == 50
        assert config.enable_iterative_search is True
        assert config.max_iterations == 3
        assert config.enable_cross_ref is True
        assert config.enable_quality_scoring is True
        assert config.deep_analysis_passes == 3
        assert config.deep_analysis_tokens == 150000


class TestOutputConfig:
    """Tests for OutputConfig model."""

    def test_default_output_config(self) -> None:
        """Test default OutputConfig values."""
        config = OutputConfig()
        assert config.format == "markdown"
        assert config.auto_save is True
        assert config.save_dir == "./reports"
        assert config.include_metadata is True

    def test_format_validation(self) -> None:
        """Test format validation."""
        # Valid formats
        config = OutputConfig(format="json")
        assert config.format == "json"

        config = OutputConfig(format="MARKDOWN")
        assert config.format == "markdown"

        # Invalid format
        with pytest.raises(ValueError):
            OutputConfig(format="invalid")


class TestDisplayConfig:
    """Tests for DisplayConfig model."""

    def test_default_display_config(self) -> None:
        """Test default DisplayConfig values."""
        config = DisplayConfig()
        assert config.color == "auto"
        assert config.progress == "auto"
        assert config.verbose is False

    def test_color_validation(self) -> None:
        """Test color validation."""
        config = DisplayConfig(color="always")
        assert config.color == "always"

        with pytest.raises(ValueError):
            DisplayConfig(color="invalid")


class TestConfig:
    """Tests for main Config model."""

    def test_default_config(self) -> None:
        """Test default Config values."""
        config = Config()
        assert isinstance(config.search, SearchConfig)
        assert isinstance(config.search_cache, SearchCacheConfig)
        assert isinstance(config.tavily, TavilyConfig)
        assert isinstance(config.research, ResearchConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.display, DisplayConfig)

    def test_config_serialization(self) -> None:
        """Test Config can be serialized."""
        config = Config()
        data = config.model_dump()

        assert "search" in data
        assert "search_cache" in data
        assert "tavily" in data
        assert "research" in data
        assert "output" in data
        assert "display" in data

    def test_config_from_dict(self) -> None:
        """Test Config can be created from dict."""
        data = {
            "search": {"depth": "quick"},
            "search_cache": {"enabled": True, "ttl_seconds": 120},
            "tavily": {"api_keys": ["test-key"]},
        }
        config = Config(**data)
        assert config.search.depth == ResearchDepth.QUICK
        assert config.search_cache.enabled is True
        assert config.search_cache.ttl_seconds == 120
        assert config.tavily.api_keys == ["test-key"]


class TestSearchCacheConfig:
    """Tests for SearchCacheConfig model."""

    def test_default_search_cache_config(self) -> None:
        """Search cache defaults should remain safe for existing installs."""
        config = SearchCacheConfig()

        assert config.enabled is False
        assert config.ttl_seconds == 3600
        assert config.max_entries == 1000
        assert config.db_path is None

    def test_resolve_db_path_uses_config_directory_by_default(self) -> None:
        """The default cache DB path should be derived from the config file location."""
        config = SearchCacheConfig()
        config_path = Path("/tmp/example/config.yaml")

        assert config.resolve_db_path(config_path) == Path("/tmp/example/search-cache.sqlite3")

    def test_resolve_db_path_respects_explicit_override(self) -> None:
        """An explicit cache DB path should take precedence over derived defaults."""
        config = SearchCacheConfig(db_path="~/cache/search.sqlite3")

        assert config.resolve_db_path(Path("/tmp/example/config.yaml")) == (
            Path("~/cache/search.sqlite3").expanduser()
        )


class TestResearchRunConfigOverrides:
    """Tests for shared config override normalization."""

    def test_applies_shared_request_overrides_without_mutating_source_config(self) -> None:
        """Request overrides should be reusable outside the CLI command body."""
        config = Config()

        updated = apply_research_request_config_overrides(
            config,
            ResearchRunRequest(
                query="test query",
                search_providers=["CLAUDE"],
                cross_reference_enabled=False,
                team_size=6,
                parallel_mode=False,
            ),
        )

        assert updated.search.providers == ["claude"]
        assert updated.research.enable_cross_ref is False
        assert updated.search_team.team_size == 6
        assert updated.search_team.parallel_execution is False

        assert config.search.providers == ["tavily"]
        assert config.research.enable_cross_ref is True
        assert config.search_team.team_size == 4
        assert config.search_team.parallel_execution is True


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_no_file(self) -> None:
        """Test loading config when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.yaml"
            config = load_config(config_path)

            # Should return default config
            assert config.search.depth == ResearchDepth.DEEP

    def test_load_config_from_file(self) -> None:
        """Test loading config from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_data = {
                "search": {"depth": "quick"},
                "tavily": {"api_keys": ["test-key"]},
            }

            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            config = load_config(config_path)
            assert config.search.depth == ResearchDepth.QUICK
            assert config.tavily.api_keys == ["test-key"]

    def test_load_config_with_env_override(self) -> None:
        """Test loading config with environment variable override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            with patch.dict(
                os.environ,
                {"TAVILY_API_KEYS": "env-key1,env-key2"},
            ):
                # Need to reload settings to pick up env var
                config = load_config(config_path)
                # Env var should override
                assert "env-key1" in config.tavily.api_keys

    def test_load_config_with_llm_env_overrides(self) -> None:
        """Test loading config with OpenRouter and Cerebras env var overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            with patch.dict(
                os.environ,
                {
                    "OPENROUTER_API_KEYS": "openrouter-1, openrouter-2",
                    "CEREBRAS_API_KEY": "cerebras-1",
                },
            ):
                config = load_config(config_path)

        assert config.llm.openrouter.api_key == "openrouter-1"
        assert config.llm.openrouter.api_keys == ["openrouter-1", "openrouter-2"]
        assert config.llm.cerebras.api_key == "cerebras-1"
        assert config.llm.cerebras.api_keys == ["cerebras-1"]


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_config(self) -> None:
        """Test saving config to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = Config()
            config.search.depth = ResearchDepth.QUICK
            config.tavily.api_keys = ["saved-key"]

            save_config(config, config_path)

            assert config_path.exists()

            # Load and verify
            with open(config_path) as f:
                data = yaml.safe_load(f)

            assert data["search"]["depth"] == "quick"
            assert data["tavily"]["api_keys"] == ["saved-key"]

    def test_save_config_creates_directory(self) -> None:
        """Test save_config creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "config.yaml"
            config = Config()

            save_config(config, config_path)

            assert config_path.exists()
            assert config_path.parent.is_dir()


class TestConfigService:
    """Tests for the shared config service."""

    def test_build_config_response_for_missing_file(self) -> None:
        """Missing config files should still yield a valid default payload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            response = build_config_response(config_path)

        assert response.file_exists is False
        assert response.config_path == str(config_path)
        assert response.persisted_config["output"]["format"] == "markdown"
        assert response.effective_config["output"]["format"] == "markdown"
        assert response.persisted_config["search_cache"]["enabled"] is False
        assert response.effective_config["search_cache"]["enabled"] is False

    def test_build_config_response_reports_runtime_overrides(self) -> None:
        """The service should distinguish persisted values from env-overridden runtime values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("output:\n  format: markdown\n", encoding="utf-8")

            with patch.dict(os.environ, {"CC_DEEP_RESEARCH_FORMAT": "json"}):
                response = build_config_response(config_path)

        assert response.persisted_config["output"]["format"] == "markdown"
        assert response.effective_config["output"]["format"] == "json"
        assert "output.format" in response.overridden_fields
        assert response.override_sources["output.format"] == ["CC_DEEP_RESEARCH_FORMAT"]

    def test_update_config_persists_partial_changes_without_touching_other_values(self) -> None:
        """A valid patch should update only the requested fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = Config()
            config.search.providers = ["tavily", "claude"]
            config.output.save_dir = "./reports"
            save_config(config, config_path)

            response = update_config(
                {
                    "output.save_dir": "./custom-reports",
                    "research.enable_cross_ref": False,
                },
                config_path=config_path,
            )
            saved = load_config(config_path)

        assert response.persisted_config["output"]["save_dir"] == "./custom-reports"
        assert saved.output.save_dir == "./custom-reports"
        assert saved.research.enable_cross_ref is False
        assert saved.search.providers == ["tavily", "claude"]

    def test_update_config_masks_and_replaces_secret_fields(self) -> None:
        """Secret updates should persist but never round-trip cleartext via the API payload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            response = update_config(
                {
                    "llm.openrouter.api_key": {
                        "action": "replace",
                        "value": "sk-secret",
                    }
                },
                config_path=config_path,
            )
            saved = load_config(config_path)

        assert response.persisted_config["llm"]["openrouter"]["api_key"] == "********"
        assert response.secret_fields
        assert saved.llm.openrouter.api_key == "sk-secret"

    def test_update_config_clears_secret_fields(self) -> None:
        """Secret clear operations should remove persisted values without exposing them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = Config()
            config.llm.openrouter.api_key = "sk-secret"
            save_config(config, config_path)

            response = update_config(
                {
                    "llm.openrouter.api_key": {
                        "action": "clear",
                    }
                },
                config_path=config_path,
            )
            saved = load_config(config_path)

        assert response.persisted_config["llm"]["openrouter"]["api_key"] is None
        assert saved.llm.openrouter.api_key is None

    def test_update_config_rejects_invalid_key(self) -> None:
        """Unknown config fields should raise a structured patch error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            with pytest.raises(ConfigPatchError) as error:
                update_config({"search.unknown_field": "value"}, config_path=config_path)

        assert error.value.fields[0].field == "search.unknown_field"

    def test_update_config_rejects_active_override_without_opt_in(self) -> None:
        """Patches should reject env-overridden fields by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            with (
                patch.dict(os.environ, {"CC_DEEP_RESEARCH_FORMAT": "json"}),
                pytest.raises(ConfigOverrideError) as error,
            ):
                update_config({"output.format": "html"}, config_path=config_path)

        assert error.value.conflicts[0].field == "output.format"


class TestGetDefaultConfigPath:
    """Tests for get_default_config_path function."""

    def test_default_path_without_xdg(self) -> None:
        """Test default path without XDG_CONFIG_HOME."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove XDG_CONFIG_HOME if set
            os.environ.pop("XDG_CONFIG_HOME", None)
            path = get_default_config_path()
            assert ".config" in str(path)
            assert "cc-deep-research" in str(path)

    def test_default_path_with_xdg(self) -> None:
        """Test default path with XDG_CONFIG_HOME."""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
            path = get_default_config_path()
            assert str(path).startswith("/custom/config")


class TestCreateDefaultConfigFile:
    """Tests for create_default_config_file function."""

    def test_create_default_config(self) -> None:
        """Test creating default config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            result_path = create_default_config_file(config_path)

            assert result_path == config_path
            assert config_path.exists()

            # Verify it's valid config
            config = load_config(config_path)
            assert isinstance(config, Config)


class TestSettings:
    """Tests for Settings model."""

    def test_default_settings(self) -> None:
        """Test default Settings values."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.config_path is None
            assert settings.depth is None
            assert settings.output_format is None
            assert settings.no_color is False

    def test_settings_from_env(self) -> None:
        """Test Settings from environment variables."""
        with patch.dict(
            os.environ,
            {
                "CC_DEEP_RESEARCH_DEPTH": "quick",
                "NO_COLOR": "1",
            },
        ):
            settings = Settings()
            assert settings.depth == ResearchDepth.QUICK
            assert settings.no_color is True


class TestParseApiKeysFromEnv:
    """Tests for _parse_api_keys_from_env function."""

    def test_parse_empty_env(self) -> None:
        """Test parsing when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove TAVILY_API_KEYS if set
            os.environ.pop("TAVILY_API_KEYS", None)
            keys = _parse_api_keys_from_env()
            assert keys == []

    def test_parse_single_key(self) -> None:
        """Test parsing single API key."""
        with patch.dict(os.environ, {"TAVILY_API_KEYS": "key1"}):
            keys = _parse_api_keys_from_env()
            assert keys == ["key1"]

    def test_parse_multiple_keys(self) -> None:
        """Test parsing multiple comma-separated keys."""
        with patch.dict(os.environ, {"TAVILY_API_KEYS": "key1,key2,key3"}):
            keys = _parse_api_keys_from_env()
            assert keys == ["key1", "key2", "key3"]

    def test_parse_keys_with_spaces(self) -> None:
        """Test parsing keys with extra spaces."""
        with patch.dict(os.environ, {"TAVILY_API_KEYS": " key1 , key2 , "}):
            keys = _parse_api_keys_from_env()
            assert keys == ["key1", "key2"]

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string."""
        with patch.dict(os.environ, {"TAVILY_API_KEYS": ""}):
            keys = _parse_api_keys_from_env()
            assert keys == []


class TestLLMAnthropicConfig:
    """Tests for LLMAnthropicConfig model."""

    def test_default_anthropic_config(self) -> None:
        """Test default LLMAnthropicConfig values."""
        config = LLMAnthropicConfig()
        assert config.enabled is False
        assert config.api_key is None
        assert config.api_keys == []
        assert config.base_url == "https://api.anthropic.com"
        assert config.timeout_seconds == 120
        assert config.model == "claude-sonnet-4-6"
        assert config.max_tokens == 512

    def test_custom_anthropic_config(self) -> None:
        """Test custom LLMAnthropicConfig values."""
        config = LLMAnthropicConfig(
            enabled=True,
            api_key="anthropic-key",
            api_keys=["anthropic-key", "anthropic-key-2"],
            timeout_seconds=90,
            model="claude-opus-4-1",
            max_tokens=1024,
        )
        assert config.enabled is True
        assert config.api_key == "anthropic-key"
        assert config.get_api_keys() == ["anthropic-key", "anthropic-key-2"]
        assert config.timeout_seconds == 90
        assert config.model == "claude-opus-4-1"
        assert config.max_tokens == 1024


class TestLLMOpenRouterConfig:
    """Tests for LLMOpenRouterConfig model."""

    def test_default_openrouter_config(self) -> None:
        """Test default LLMOpenRouterConfig values."""
        config = LLMOpenRouterConfig()
        assert config.enabled is False
        assert config.api_key is None
        assert config.api_keys == []
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.timeout_seconds == 120
        assert config.model == "anthropic/claude-sonnet-4"

    def test_custom_openrouter_config(self) -> None:
        """Test custom LLMOpenRouterConfig values."""
        config = LLMOpenRouterConfig(
            enabled=True,
            api_key="sk-test-key",
            api_keys=["sk-test-key", "sk-second-key"],
            base_url="https://custom.openrouter.ai/v1",
            timeout_seconds=60,
            model="openai/gpt-4",
            extra_headers={"X-Custom": "value"},
        )
        assert config.enabled is True
        assert config.api_key == "sk-test-key"
        assert config.get_api_keys() == ["sk-test-key", "sk-second-key"]
        assert config.base_url == "https://custom.openrouter.ai/v1"
        assert config.extra_headers == {"X-Custom": "value"}


class TestLLMCerebrasConfig:
    """Tests for LLMCerebrasConfig model."""

    def test_default_cerebras_config(self) -> None:
        """Test default LLMCerebrasConfig values."""
        config = LLMCerebrasConfig()
        assert config.enabled is False
        assert config.api_key is None
        assert config.api_keys == []
        assert config.base_url == "https://api.cerebras.ai/v1"
        assert config.timeout_seconds == 60
        assert config.model == "llama-3.3-70b"

    def test_custom_cerebras_config(self) -> None:
        """Test custom LLMCerebrasConfig values."""
        config = LLMCerebrasConfig(
            enabled=True,
            api_key="cerebras-key",
            api_keys=["cerebras-key", "cerebras-key-2"],
            timeout_seconds=30,
            model="llama-3.1-8b",
        )
        assert config.enabled is True
        assert config.api_key == "cerebras-key"
        assert config.get_api_keys() == ["cerebras-key", "cerebras-key-2"]
        assert config.timeout_seconds == 30


class TestLLMRouteDefaults:
    """Tests for LLMRouteDefaults model."""

    def test_default_route_defaults(self) -> None:
        """Test default LLMRouteDefaults values."""
        defaults = LLMRouteDefaults()
        assert defaults.analyzer == "anthropic"
        assert defaults.deep_analyzer == "anthropic"
        assert defaults.report_quality_evaluator == "anthropic"
        assert defaults.reporter == "anthropic"
        assert defaults.default == "anthropic"

    def test_custom_route_defaults(self) -> None:
        """Test custom LLMRouteDefaults values."""
        defaults = LLMRouteDefaults(
            analyzer="openrouter",
            deep_analyzer="cerebras",
            default="heuristic",
        )
        assert defaults.analyzer == "openrouter"
        assert defaults.deep_analyzer == "cerebras"
        assert defaults.default == "heuristic"


class TestLLMConfig:
    """Tests for LLMConfig model."""

    def test_default_llm_config(self) -> None:
        """Test default LLMConfig values."""
        config = LLMConfig()
        assert isinstance(config.openrouter, LLMOpenRouterConfig)
        assert isinstance(config.cerebras, LLMCerebrasConfig)
        assert isinstance(config.anthropic, LLMAnthropicConfig)
        assert isinstance(config.route_defaults, LLMRouteDefaults)
        assert config.openrouter.enabled is False
        assert config.cerebras.enabled is False
        assert config.anthropic.enabled is False

    def test_get_enabled_transports_default(self) -> None:
        """Test get_enabled_transports with default config."""
        config = LLMConfig()
        transports = config.get_enabled_transports()
        assert "anthropic" not in transports
        assert "heuristic" in transports
        assert "openrouter" not in transports
        assert "cerebras" not in transports

    def test_get_enabled_transports_with_api_keys(self) -> None:
        """Test get_enabled_transports with API keys configured."""
        config = LLMConfig(
            openrouter=LLMOpenRouterConfig(enabled=True, api_key="test-key"),
            cerebras=LLMCerebrasConfig(enabled=True, api_key="cerebras-key"),
        )
        transports = config.get_enabled_transports()
        assert "openrouter" in transports
        assert "cerebras" in transports
        assert "heuristic" in transports

    def test_get_enabled_transports_with_api_key_lists(self) -> None:
        """Test get_enabled_transports with multi-key provider configs."""
        config = LLMConfig(
            openrouter=LLMOpenRouterConfig(enabled=True, api_keys=["test-key-1", "test-key-2"]),
            cerebras=LLMCerebrasConfig(enabled=True, api_keys=["cerebras-key-1"]),
        )

        transports = config.get_enabled_transports()

        assert "openrouter" in transports
        assert "cerebras" in transports

    def test_get_enabled_transports_respects_fallback_order(self) -> None:
        """Test get_enabled_transports respects fallback order."""
        config = LLMConfig(
            fallback_order=["cerebras", "openrouter", "anthropic", "heuristic"],
            openrouter=LLMOpenRouterConfig(enabled=True, api_key="test-key"),
            cerebras=LLMCerebrasConfig(enabled=True, api_key="cerebras-key"),
        )
        transports = config.get_enabled_transports()
        assert transports[0] == "cerebras"
        assert transports[1] == "openrouter"
        assert transports[2] == "heuristic"

    def test_get_route_for_agent(self) -> None:
        """Test get_route_for_agent returns correct route."""
        config = LLMConfig(
            route_defaults=LLMRouteDefaults(
                analyzer="openrouter",
                deep_analyzer="cerebras",
            )
        )
        assert config.get_route_for_agent("analyzer") == "openrouter"
        assert config.get_route_for_agent("deep_analyzer") == "cerebras"
        assert config.get_route_for_agent("unknown_agent") == "anthropic"

    def test_llm_config_in_main_config(self) -> None:
        """Test LLMConfig is included in main Config."""
        config = Config()
        assert isinstance(config.llm, LLMConfig)
        assert config.llm.anthropic.enabled is False

    def test_llm_config_serialization(self) -> None:
        """Test LLMConfig can be serialized."""
        config = Config(
            llm=LLMConfig(
                openrouter=LLMOpenRouterConfig(enabled=True, api_key="test-key"),
            )
        )
        data = config.model_dump()
        assert "llm" in data
        assert data["llm"]["openrouter"]["enabled"] is True
        assert data["llm"]["openrouter"]["api_key"] == "test-key"

    def test_llm_config_from_dict(self) -> None:
        """Test Config can be created with LLM config from dict."""
        data = {
            "llm": {
                "anthropic": {"enabled": True, "api_key": "anthropic-key"},
                "openrouter": {"enabled": True, "api_key": "test-key"},
            }
        }
        config = Config(**data)
        assert config.llm.anthropic.enabled is True
        assert config.llm.anthropic.api_key == "anthropic-key"
        assert config.llm.openrouter.enabled is True
        assert config.llm.openrouter.api_key == "test-key"
