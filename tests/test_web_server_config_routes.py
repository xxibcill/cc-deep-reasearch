"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.web_server import (
    create_app,
)


def test_get_config_returns_masked_persisted_and_effective_state(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The config read endpoint should expose masked values and override metadata."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "output:\n  format: markdown\nllm:\n  openrouter:\n    api_key: sk-test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CC_DEEP_RESEARCH_FORMAT", "json")

    client = TestClient(create_app())
    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted_config"]["output"]["format"] == "markdown"
    assert payload["effective_config"]["output"]["format"] == "json"
    assert payload["persisted_config"]["llm"]["openrouter"]["api_key"] == "********"
    assert "output.format" in payload["overridden_fields"]


def test_patch_config_persists_updates_and_returns_refreshed_payload(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The config patch endpoint should save valid partial updates."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.patch(
        "/api/config",
        json={
            "updates": {
                "output.save_dir": "./custom-reports",
                "research.enable_cross_ref": False,
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted_config"]["output"]["save_dir"] == "./custom-reports"
    assert payload["persisted_config"]["research"]["enable_cross_ref"] is False


def test_patch_config_clears_secret_fields(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The config patch endpoint should support explicit secret clear actions."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEYS", raising=False)
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "llm:\n  openrouter:\n    api_key: sk-test\n",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.patch(
        "/api/config",
        json={
            "updates": {
                "llm.openrouter.api_key": {
                    "action": "clear",
                }
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted_config"]["llm"]["openrouter"]["api_key"] is None


def test_patch_config_returns_structured_field_errors(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid field paths should return a 400 with field-level errors."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.patch(
        "/api/config",
        json={"updates": {"search.invalid": "value"}},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["fields"][0]["field"] == "search.invalid"


def test_patch_config_returns_override_conflicts(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patching an env-overridden field should return a 409 conflict."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("CC_DEEP_RESEARCH_FORMAT", "json")

    client = TestClient(create_app())
    response = client.patch(
        "/api/config",
        json={"updates": {"output.format": "html"}},
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["conflicts"][0]["field"] == "output.format"
