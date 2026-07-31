"""Inspect the effective Codex SDK configuration used by the provider runtime."""

from __future__ import annotations

from typing import Any

from openai_codex.generated.v2_all import (
    ConfigReadResponse,
    ListMcpServerStatusResponse,
)

from cc_deep_research.llm.codex_security import effective_security_config_is_safe
from cc_deep_research.llm.codex_types import CodexRuntimeUnavailableError


async def validate_effective_security(client: Any) -> None:
    """Fail closed when higher-precedence Codex config defeats isolation."""
    async_client = client._client
    sync_client = async_client._sync
    config_response = await async_client._call_sync(
        sync_client.request,
        "config/read",
        {"cwd": None, "includeLayers": False},
        response_model=ConfigReadResponse,
    )
    effective_config = config_response.config.model_dump(
        mode="json",
        by_alias=False,
        exclude_none=True,
    )
    if not effective_security_config_is_safe(effective_config):
        raise CodexRuntimeUnavailableError(
            "Effective Codex configuration does not preserve provider isolation."
        )

    cursor: str | None = None
    while True:
        status_response = await async_client._call_sync(
            sync_client.request,
            "mcpServerStatus/list",
            {
                "cursor": cursor,
                "detail": "toolsAndAuthOnly",
                "limit": 100,
                "threadId": None,
            },
            response_model=ListMcpServerStatusResponse,
        )
        if any(
            server.server_info is not None
            or bool(server.tools)
            or bool(server.resources)
            or bool(server.resource_templates)
            for server in status_response.data
        ):
            raise CodexRuntimeUnavailableError(
                "Effective Codex MCP configuration is not isolated."
            )
        cursor = status_response.next_cursor
        if cursor is None:
            return
