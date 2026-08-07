"""Integration tests for Kimi configuration and route wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cc_deep_research.config import Config, LLMKimiConfig, load_config
from cc_deep_research.config.service import build_config_response
from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMTransportType,
    transport_from_route_name,
)
from cc_deep_research.llm.kimi import KimiTransport
from cc_deep_research.llm.registry import LLMRouteRegistry
from cc_deep_research.llm.router import LLMRouter
from cc_deep_research.orchestration.llm_route_planner import LLMRoutePlanner


def configured_kimi() -> Config:
    """Return an application config with Kimi selected for every route."""
    config = Config()
    config.llm.kimi = LLMKimiConfig(
        enabled=True,
        api_keys=["kimi-key-1", "kimi-key-2"],
        model="kimi-k3",
        reasoning_effort="high",
        timeout_seconds=240,
    )
    config.llm.fallback_order = ["kimi", "heuristic"]
    config.llm.route_defaults.analyzer = "kimi"
    config.llm.route_defaults.default = "kimi"
    return config


def test_kimi_config_defaults_and_route_name() -> None:
    config = LLMKimiConfig()

    assert config.enabled is False
    assert config.base_url == "https://api.moonshot.ai/v1"
    assert config.model == "kimi-k3"
    assert config.reasoning_effort == "max"
    assert config.timeout_seconds == 300
    assert transport_from_route_name("kimi") == LLMTransportType.KIMI_API


def test_kimi_config_normalizes_multiple_keys() -> None:
    config = LLMKimiConfig(
        api_key=" key-1 ",
        api_keys=["key-1", "key-2", ""],
    )

    assert config.get_api_keys() == ["key-1", "key-2"]


def test_kimi_environment_uses_official_moonshot_name(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOONSHOT_API_KEY", "moonshot-env-key")
    monkeypatch.delenv("MOONSHOT_API_KEYS", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEYS", raising=False)

    config = load_config(tmp_path / "missing.yaml")

    assert config.llm.kimi.api_key == "moonshot-env-key"
    assert config.llm.kimi.api_keys == ["moonshot-env-key"]


def test_kimi_environment_accepts_alias_and_preserves_priority(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOONSHOT_API_KEYS", "official-1,official-2")
    monkeypatch.setenv("KIMI_API_KEY", "alias-1")
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEYS", raising=False)

    config = load_config(tmp_path / "missing.yaml")

    assert config.llm.kimi.get_api_keys() == ["official-1", "official-2", "alias-1"]


def test_registry_builds_kimi_route_with_provider_settings() -> None:
    config = configured_kimi()
    registry = LLMRouteRegistry(config.llm)

    route = registry.get_route("analyzer")

    assert route.transport == LLMTransportType.KIMI_API
    assert route.provider == LLMProviderType.KIMI
    assert route.model == "kimi-k3"
    assert route.timeout_seconds == 240
    assert route.extra["api_keys"] == ["kimi-key-1", "kimi-key-2"]
    assert route.extra["reasoning_effort"] == "high"


def test_router_creates_kimi_transport() -> None:
    registry = LLMRouteRegistry(configured_kimi().llm)
    router = LLMRouter(registry)

    transport = router.get_transport("analyzer")

    assert isinstance(transport, KimiTransport)


def test_planner_selects_enabled_kimi_route() -> None:
    config = configured_kimi()
    planner = LLMRoutePlanner(config)

    plan = planner.plan_routes(MagicMock())

    assert plan.default_route.transport == LLMTransportType.KIMI_API
    assert plan.default_route.provider == LLMProviderType.KIMI
    assert plan.agent_routes["analyzer"].transport == LLMTransportType.KIMI_API
    assert plan.fallback_order == [LLMTransportType.KIMI_API, LLMTransportType.HEURISTIC]


def test_dashboard_config_masks_kimi_secrets(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "MOONSHOT_API_KEY",
        "MOONSHOT_API_KEYS",
        "KIMI_API_KEY",
        "KIMI_API_KEYS",
    ):
        monkeypatch.delenv(name, raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "llm:\n  kimi:\n    enabled: true\n    api_key: secret-kimi-key\n",
        encoding="utf-8",
    )

    response = build_config_response(config_path)
    fields = {field.field: field for field in response.secret_fields}

    assert response.persisted_config["llm"]["kimi"]["api_key"] == "********"
    assert fields["llm.kimi.api_key"].persisted_present is True
    assert fields["llm.kimi.api_key"].persisted_count == 1
