"""Tests for the Codex SDK effective-configuration probe."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from cc_deep_research.llm.codex_security import provider_config
from cc_deep_research.llm.codex_security_probe import validate_effective_security
from cc_deep_research.llm.codex_types import CodexRuntimeUnavailableError


class _Config:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self._values


class _ProbeClient:
    def __init__(self, config: dict[str, Any], servers: list[Any]) -> None:
        self._sync = SimpleNamespace(request=object())
        self._config = config
        self._servers = servers
        self.calls: list[str] = []

    async def _call_sync(
        self,
        _request: Any,
        method: str,
        _params: dict[str, Any],
        *,
        response_model: Any,
    ) -> Any:
        del response_model
        self.calls.append(method)
        if method == "config/read":
            return SimpleNamespace(config=_Config(self._config))
        return SimpleNamespace(data=self._servers, next_cursor=None)


def _client(config: dict[str, Any], servers: list[Any] | None = None) -> Any:
    return SimpleNamespace(_client=_ProbeClient(config, servers or []))


@pytest.mark.asyncio
async def test_effective_security_probe_accepts_isolated_runtime() -> None:
    client = _client(provider_config())

    await validate_effective_security(client)

    assert client._client.calls == ["config/read", "mcpServerStatus/list"]


@pytest.mark.asyncio
async def test_effective_security_probe_rejects_unsafe_config() -> None:
    unsafe_config = {**provider_config(), "web_search": "live"}

    with pytest.raises(CodexRuntimeUnavailableError, match="does not preserve"):
        await validate_effective_security(_client(unsafe_config))


@pytest.mark.asyncio
async def test_effective_security_probe_rejects_available_mcp_capabilities() -> None:
    server = SimpleNamespace(
        server_info=SimpleNamespace(name="docs"),
        tools=[],
        resources=[],
        resource_templates=[],
    )

    with pytest.raises(CodexRuntimeUnavailableError, match="MCP"):
        await validate_effective_security(_client(provider_config(), [server]))
