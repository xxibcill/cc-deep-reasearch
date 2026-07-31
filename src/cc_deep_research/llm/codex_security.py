"""Fail-closed security policy for Codex app-server provider processes."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cc_deep_research.llm.codex_types import CodexRuntimeUnavailableError

PROVIDER_INSTRUCTIONS = """\
Operate only as a text-generation provider.
Do not invoke shell commands, filesystem operations, web search, browser tools,
apps, MCP tools, image generation, or any other tools. Return only the requested
final text.
"""
_PROVIDER_CONFIG_OVERRIDES = (
    "allow_login_shell=false",
    'forced_login_method="chatgpt"',
    'history.persistence="none"',
    "memories.generate_memories=false",
    "memories.use_memories=false",
    "notify=[]",
    'otel.exporter="none"',
    "otel.log_user_prompt=false",
    'otel.metrics_exporter="none"',
    'otel.trace_exporter="none"',
    "shell_environment_policy.experimental_use_profile=false",
    "shell_environment_policy.ignore_default_excludes=false",
    'shell_environment_policy.inherit="none"',
    "tools.view_image=false",
    "tools.web_search=false",
    'web_search="disabled"',
    "features.auth_elicitation=false",
    "features.apps=false",
    "features.browser_use=false",
    "features.browser_use_external=false",
    "features.browser_use_full_cdp_access=false",
    "features.code_mode=false",
    "features.code_mode_host=false",
    "features.computer_use=false",
    "features.goals=false",
    "features.hooks=false",
    "features.image_generation=false",
    "features.in_app_browser=false",
    "features.js_repl=false",
    "features.memories=false",
    "features.multi_agent=false",
    "features.network_proxy=false",
    "features.plugins=false",
    "features.remote_plugin=false",
    "features.remote_control=false",
    "features.shell_snapshot=false",
    "features.shell_tool=false",
    "features.skill_mcp_dependency_install=false",
    "features.standalone_web_search=false",
    "features.tool_suggest=false",
    "features.unified_exec=false",
    "features.workspace_dependencies=false",
)
_REQUIRED_DISABLED_FEATURES = frozenset(
    {
        "apps",
        "auth_elicitation",
        "browser_use",
        "browser_use_external",
        "browser_use_full_cdp_access",
        "code_mode",
        "code_mode_host",
        "computer_use",
        "goals",
        "hooks",
        "image_generation",
        "in_app_browser",
        "js_repl",
        "memories",
        "multi_agent",
        "network_proxy",
        "plugins",
        "remote_control",
        "remote_plugin",
        "shell_snapshot",
        "shell_tool",
        "skill_mcp_dependency_install",
        "standalone_web_search",
        "tool_suggest",
        "unified_exec",
        "workspace_dependencies",
    }
)


def provider_config() -> dict[str, Any]:
    """Return a fresh, tool-disabled configuration for one provider thread."""
    return {
        "allow_login_shell": False,
        "forced_login_method": "chatgpt",
        "history": {"persistence": "none"},
        "memories": {
            "generate_memories": False,
            "use_memories": False,
        },
        "notify": [],
        "otel": {
            "exporter": "none",
            "log_user_prompt": False,
            "metrics_exporter": "none",
            "trace_exporter": "none",
        },
        "shell_environment_policy": {
            "experimental_use_profile": False,
            "ignore_default_excludes": False,
            "inherit": "none",
        },
        "tools": {
            "view_image": False,
            "web_search": False,
        },
        "web_search": "disabled",
        "features": dict.fromkeys(_REQUIRED_DISABLED_FEATURES, False),
    }


def provider_process_overrides() -> tuple[str, ...]:
    """Disable inherited runtime tools, including named user MCP servers."""
    configured_home = os.environ.get("CODEX_HOME")
    codex_home = Path(configured_home).expanduser() if configured_home else Path.home() / ".codex"
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        return _PROVIDER_CONFIG_OVERRIDES

    try:
        with config_path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CodexRuntimeUnavailableError(
            "Codex configuration could not be inspected safely."
        ) from exc

    raw_servers = raw_config.get("mcp_servers")
    if not isinstance(raw_servers, dict):
        return _PROVIDER_CONFIG_OVERRIDES

    server_names = tuple(str(server_name) for server_name in sorted(raw_servers, key=str))
    if any(
        not server_name
        or not all(character.isalnum() or character in {"-", "_"} for character in server_name)
        for server_name in server_names
    ):
        raise CodexRuntimeUnavailableError(
            "Codex MCP configuration contains an unsupported server name."
        )

    disabled_servers: list[str] = []
    for server_name in server_names:
        raw_server = raw_servers[server_name]
        if not isinstance(raw_server, dict):
            raise CodexRuntimeUnavailableError(
                "Codex MCP configuration has an unsupported server definition."
            )
        has_command = "command" in raw_server
        has_url = "url" in raw_server
        if has_command == has_url:
            raise CodexRuntimeUnavailableError(
                "Codex MCP configuration has an unsupported transport."
            )
        disabled_transport = (
            'command="codex-provider-disabled"'
            if has_command
            else 'url="http://127.0.0.1:9/codex-provider-disabled"'
        )
        disabled_servers.append(f"mcp_servers.{server_name}={{enabled=false,{disabled_transport}}}")
    return (*_PROVIDER_CONFIG_OVERRIDES, *disabled_servers)


def effective_security_config_is_safe(config: Mapping[str, Any]) -> bool:
    """Return whether effective app-server config preserves provider isolation."""
    if config.get("approval_policy") not in (None, "never"):
        return False
    if config.get("sandbox_mode") not in (None, "read-only"):
        return False
    if config.get("forced_login_method") != "chatgpt":
        return False
    if config.get("model_provider") not in (None, "openai"):
        return False
    if config.get("web_search") != "disabled":
        return False
    if config.get("notify") != []:
        return False

    tools = config.get("tools")
    if not isinstance(tools, Mapping):
        return False
    if tools.get("view_image", False) is not False:
        return False
    if tools.get("web_search", False) is not False:
        return False

    otel = config.get("otel")
    if not isinstance(otel, Mapping):
        return False
    if otel.get("log_user_prompt") is not False:
        return False
    if any(
        otel.get(exporter) != "none"
        for exporter in ("exporter", "metrics_exporter", "trace_exporter")
    ):
        return False

    shell_policy = config.get("shell_environment_policy")
    if not isinstance(shell_policy, Mapping):
        return False
    if shell_policy.get("inherit") != "none":
        return False
    if shell_policy.get("experimental_use_profile") is not False:
        return False
    if shell_policy.get("ignore_default_excludes") is not False:
        return False

    features = config.get("features")
    if not isinstance(features, Mapping):
        return False
    if any(features.get(feature) is not False for feature in _REQUIRED_DISABLED_FEATURES):
        return False

    mcp_servers = config.get("mcp_servers", {})
    if not isinstance(mcp_servers, Mapping):
        return False
    return all(
        isinstance(server, Mapping) and server.get("enabled") is False
        for server in mcp_servers.values()
    )


__all__ = [
    "PROVIDER_INSTRUCTIONS",
    "effective_security_config_is_safe",
    "provider_config",
    "provider_process_overrides",
]
