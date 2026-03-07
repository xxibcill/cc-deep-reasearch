"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from cc_deep_research.config import (
    Config,
    DisplayConfig,
    OutputConfig,
    ResearchConfig,
    SearchConfig,
    Settings,
    TavilyConfig,
    _parse_api_keys_from_env,
    create_default_config_file,
    get_default_config_path,
    load_config,
    save_config,
)
from cc_deep_research.models import ResearchDepth, SearchMode


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
        assert isinstance(config.tavily, TavilyConfig)
        assert isinstance(config.research, ResearchConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.display, DisplayConfig)

    def test_config_serialization(self) -> None:
        """Test Config can be serialized."""
        config = Config()
        data = config.model_dump()

        assert "search" in data
        assert "tavily" in data
        assert "research" in data
        assert "output" in data
        assert "display" in data

    def test_config_from_dict(self) -> None:
        """Test Config can be created from dict."""
        data = {
            "search": {"depth": "quick"},
            "tavily": {"api_keys": ["test-key"]},
        }
        config = Config(**data)
        assert config.search.depth == ResearchDepth.QUICK
        assert config.tavily.api_keys == ["test-key"]


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
