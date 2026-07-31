"""Shared lifecycle and authentication boundary for the Codex app-server."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
import tomllib
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai_codex import (
    ApprovalMode,
    AsyncCodex,
    CodexConfig,
    Sandbox,
    TransportClosedError,
)
from openai_codex.generated.v2_all import (
    ConfigReadResponse,
    ListMcpServerStatusResponse,
)
from openai_codex.types import ReasoningEffort

logger = logging.getLogger(__name__)

_PROVIDER_INSTRUCTIONS = """\
Operate only as a text-generation provider.
Do not invoke shell commands, filesystem operations, web search, browser tools,
apps, MCP tools, image generation, or any other tools. Return only the requested
final text.
"""
_PROVIDER_CONFIG_OVERRIDES = (
    "allow_login_shell=false",
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
_TURN_INTERRUPT_TIMEOUT_SECONDS = 5.0
_CLIENT_CLOSE_TIMEOUT_SECONDS = 5.0
_RUNTIME_CONTROL_TIMEOUT_SECONDS = 30.0
_START_RETRY_DELAY_SECONDS = 5.0


class CodexRuntimeError(RuntimeError):
    """Base error raised by the managed Codex runtime."""


class CodexRuntimeUnavailableError(CodexRuntimeError):
    """Raised when the local Codex app-server cannot be started or reached."""


class CodexNotAuthenticatedError(CodexRuntimeError):
    """Raised when a Codex turn is requested without an authenticated account."""


class CodexLoginConflictError(CodexRuntimeError):
    """Raised when another interactive Codex login is already active."""


class CodexLoginNotFoundError(CodexRuntimeError):
    """Raised when a login identifier is unknown to this runtime."""


@dataclass(frozen=True, slots=True)
class CodexAccountSnapshot:
    """Safe, immutable account state suitable for API serialization."""

    runtime_status: str
    authenticated: bool
    requires_openai_auth: bool | None
    account_type: str | None
    email: str | None
    plan_type: str | None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class CodexLoginSnapshot:
    """Safe, immutable state for one managed interactive login."""

    login_id: str
    flow: str
    status: str
    auth_url: str | None
    verification_url: str | None
    user_code: str | None
    error: str | None
    created_at: str
    completed_at: str | None


@dataclass(frozen=True, slots=True)
class CodexTurnResult:
    """Provider-neutral result returned by :class:`CodexRuntime`."""

    content: str
    model: str
    turn_id: str
    duration_ms: int
    finish_reason: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_output_tokens: int = 0


@dataclass(slots=True)
class _LoginAttempt:
    snapshot: CodexLoginSnapshot
    handle: Any
    client: Any
    waiter: asyncio.Task[None] | None = None
    terminal_snapshot: CodexLoginSnapshot | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    raw_value = getattr(value, "value", value)
    return str(raw_value)


def _provider_config() -> dict[str, Any]:
    """Return a fresh, tool-disabled configuration for one provider thread."""
    return {
        "allow_login_shell": False,
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
        "features": {
            "apps": False,
            "auth_elicitation": False,
            "browser_use": False,
            "browser_use_external": False,
            "browser_use_full_cdp_access": False,
            "code_mode": False,
            "code_mode_host": False,
            "computer_use": False,
            "goals": False,
            "hooks": False,
            "image_generation": False,
            "in_app_browser": False,
            "js_repl": False,
            "memories": False,
            "multi_agent": False,
            "network_proxy": False,
            "plugins": False,
            "remote_plugin": False,
            "remote_control": False,
            "shell_snapshot": False,
            "shell_tool": False,
            "skill_mcp_dependency_install": False,
            "standalone_web_search": False,
            "tool_suggest": False,
            "unified_exec": False,
            "workspace_dependencies": False,
        },
    }


def _provider_process_overrides() -> tuple[str, ...]:
    """Disable inherited runtime tools, including named user MCP servers."""
    configured_home = os.environ.get("CODEX_HOME")
    codex_home = (
        Path(configured_home).expanduser()
        if configured_home
        else Path.home() / ".codex"
    )
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
        disabled_servers.append(
            f"mcp_servers.{server_name}={{enabled=false,{disabled_transport}}}"
        )
    return (*_PROVIDER_CONFIG_OVERRIDES, *disabled_servers)


def _effective_security_config_is_safe(config: Mapping[str, Any]) -> bool:
    """Return whether effective app-server config preserves provider isolation."""
    if config.get("approval_policy") not in (None, "never"):
        return False
    if config.get("sandbox_mode") not in (None, "read-only"):
        return False
    if config.get("forced_login_method") not in (None, "chatgpt"):
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


class CodexRuntime:
    """Own one async Codex SDK client, its auth state, and active login handles."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any] | None = None,
        isolated_cwd: str | Path | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._configured_cwd = Path(isolated_cwd).expanduser() if isolated_cwd else None
        self._temporary_cwd: tempfile.TemporaryDirectory[str] | None = None
        self._client: Any | None = None
        self._owner_loop: asyncio.AbstractEventLoop | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._account_lock = asyncio.Lock()
        self._auth_operation_lock = asyncio.Lock()
        self._login_lock = asyncio.Lock()
        self._logins: dict[str, _LoginAttempt] = {}
        self._active_login_id: str | None = None
        self._default_model: str | None = None
        self._next_start_attempt = 0.0
        self._account_snapshot = CodexAccountSnapshot(
            runtime_status="stopped",
            authenticated=False,
            requires_openai_auth=None,
            account_type=None,
            email=None,
            plan_type=None,
        )

    @property
    def account_snapshot(self) -> CodexAccountSnapshot:
        """Return the latest immutable account snapshot."""
        return self._account_snapshot

    @property
    def is_authenticated(self) -> bool:
        """Return whether the most recent account read found an account."""
        return self._account_snapshot.authenticated

    @property
    def runtime_status(self) -> str:
        """Return the current lifecycle status."""
        return self._account_snapshot.runtime_status

    @property
    def default_model(self) -> str | None:
        """Return the model currently marked as default by Codex, when known."""
        return self._default_model

    @property
    def can_attempt_start(self) -> bool:
        """Return whether a stopped or transiently failed runtime may start."""
        if self._account_snapshot.runtime_status in {"stopped", "starting"}:
            return True
        return (
            self._account_snapshot.runtime_status == "error"
            and time.monotonic() >= self._next_start_attempt
        )

    @property
    def isolated_cwd(self) -> Path | None:
        """Return the empty working directory used for provider turns."""
        if self._configured_cwd is not None:
            return self._configured_cwd
        if self._temporary_cwd is None:
            return None
        return Path(self._temporary_cwd.name)

    async def start(self) -> None:
        """Start the SDK client and preflight account state.

        Startup is idempotent and deliberately non-fatal. Callers that require
        the runtime use :meth:`_ensure_started`, which turns a recorded startup
        failure into a typed exception.
        """
        current_loop = asyncio.get_running_loop()
        if self._owner_loop is None or (
            self._owner_loop.is_closed() and self._client is None
        ):
            self._owner_loop = current_loop

        async with self._lifecycle_lock:
            if self._client is not None:
                return
            if not self.can_attempt_start:
                return

            self._account_snapshot = replace(
                self._account_snapshot,
                runtime_status="starting",
                error_code=None,
                error_message=None,
            )
            self._ensure_isolated_cwd()
            client: Any | None = None

            try:
                client = self._create_client()
                async with asyncio.timeout(_RUNTIME_CONTROL_TIMEOUT_SECONDS):
                    account_response = await client.account()
                    if self._client_factory is None:
                        await self._validate_effective_security(client)
                    account_snapshot = self._snapshot_from_account(account_response)
                    if account_snapshot.authenticated:
                        await self._refresh_default_model(client)
            except asyncio.CancelledError:
                if client is not None:
                    await self._safe_close_client(client)
                self._cleanup_temporary_cwd()
                self._account_snapshot = CodexAccountSnapshot(
                    runtime_status="stopped",
                    authenticated=False,
                    requires_openai_auth=None,
                    account_type=None,
                    email=None,
                    plan_type=None,
                )
                raise
            except Exception as exc:
                if client is not None:
                    await self._safe_close_client(client)
                self._cleanup_temporary_cwd()
                status = "unavailable" if isinstance(exc, FileNotFoundError) else "error"
                self._account_snapshot = CodexAccountSnapshot(
                    runtime_status=status,
                    authenticated=False,
                    requires_openai_auth=None,
                    account_type=None,
                    email=None,
                    plan_type=None,
                    error_code=type(exc).__name__,
                    error_message="Codex runtime could not be started.",
                )
                logger.warning(
                    "Codex runtime startup failed (%s)",
                    type(exc).__name__,
                )
                self._next_start_attempt = (
                    time.monotonic() + _START_RETRY_DELAY_SECONDS
                    if status == "error"
                    else float("inf")
                )
                return

            assert client is not None
            self._client = client
            self._next_start_attempt = 0.0
            self._account_snapshot = account_snapshot

    async def close(self) -> None:
        """Cancel pending logins and close the managed SDK process."""
        async with self._auth_operation_lock:
            async with self._login_lock:
                active_login_id = self._active_login_id
            if active_login_id is not None:
                with suppress(CodexRuntimeError):
                    await self._cancel_login(active_login_id)

            async with self._lifecycle_lock:
                client = self._client
                self._client = None
                if client is not None:
                    self._account_snapshot = replace(
                        self._account_snapshot,
                        runtime_status="closing",
                    )
                    await self._safe_close_client(client)

                self._default_model = None
                self._next_start_attempt = 0.0
                self._cleanup_temporary_cwd()
                self._account_snapshot = CodexAccountSnapshot(
                    runtime_status="stopped",
                    authenticated=False,
                    requires_openai_auth=None,
                    account_type=None,
                    email=None,
                    plan_type=None,
                )

            await self._finish_pending_logins_for_shutdown()

    async def refresh_account(
        self,
        *,
        refresh_token: bool = False,
    ) -> CodexAccountSnapshot:
        """Read account state from Codex and refresh the safe snapshot."""
        async with self._auth_operation_lock:
            return await self._refresh_account(refresh_token=refresh_token)

    async def _refresh_account(
        self,
        *,
        refresh_token: bool = False,
    ) -> CodexAccountSnapshot:
        """Read account state while the caller owns the auth-operation lock."""
        client = await self._ensure_started()
        async with self._account_lock:
            try:
                async with asyncio.timeout(_RUNTIME_CONTROL_TIMEOUT_SECONDS):
                    response = await client.account(refresh_token=refresh_token)
            except (TimeoutError, TransportClosedError) as exc:
                await self._discard_client(client)
                raise CodexRuntimeUnavailableError(
                    "Codex runtime account request did not complete."
                ) from exc
            except Exception as exc:
                self._account_snapshot = replace(
                    self._account_snapshot,
                    runtime_status="error",
                    error_code=type(exc).__name__,
                    error_message="Unable to read Codex account.",
                )
                logger.warning("Codex account read failed (%s)", type(exc).__name__)
                raise CodexRuntimeError("Unable to read Codex account.") from exc

            self._account_snapshot = self._snapshot_from_account(response)
            if self._account_snapshot.authenticated:
                try:
                    await self._refresh_default_model(client)
                except (TimeoutError, TransportClosedError) as exc:
                    await self._discard_client(client)
                    raise CodexRuntimeUnavailableError(
                        "Codex runtime model discovery did not complete."
                    ) from exc
            else:
                self._default_model = None
            return self._account_snapshot

    async def login_browser(self) -> CodexLoginSnapshot:
        """Start managed browser-based ChatGPT login."""
        return await self._start_login("browser")

    async def login_device_code(self) -> CodexLoginSnapshot:
        """Start managed device-code ChatGPT login."""
        return await self._start_login("device_code")

    async def get_active_login(self) -> CodexLoginSnapshot | None:
        """Return the safe snapshot for the active login ceremony, if any."""
        async with self._login_lock:
            if self._active_login_id is None:
                return None
            attempt = self._logins.get(self._active_login_id)
            if attempt is None:
                return None
            return attempt.terminal_snapshot or attempt.snapshot

    def get_login(self, login_id: str) -> CodexLoginSnapshot:
        """Return a safe snapshot for a known login attempt."""
        attempt = self._logins.get(login_id)
        if attempt is None:
            raise CodexLoginNotFoundError(f"Unknown Codex login: {login_id}")
        return attempt.snapshot

    async def cancel_login(self, login_id: str) -> CodexLoginSnapshot:
        """Cancel a pending login and return its terminal snapshot."""
        async with self._auth_operation_lock:
            return await self._cancel_login(login_id)

    async def _cancel_login(self, login_id: str) -> CodexLoginSnapshot:
        """Cancel one login while the caller owns the auth-operation lock."""
        async with self._login_lock:
            attempt = self._logins.get(login_id)
            if attempt is None:
                raise CodexLoginNotFoundError(f"Unknown Codex login: {login_id}")
            if attempt.snapshot.status not in {"pending", "canceling"}:
                return attempt.snapshot
            attempt.snapshot = replace(attempt.snapshot, status="canceling")

        try:
            async with asyncio.timeout(_RUNTIME_CONTROL_TIMEOUT_SECONDS):
                await attempt.handle.cancel()
        except asyncio.CancelledError:
            waiter: asyncio.Task[None] | None = None
            should_discard_client = False
            should_refresh_account = False
            async with self._login_lock:
                terminal_snapshot = attempt.terminal_snapshot
                if terminal_snapshot is not None:
                    attempt.snapshot = terminal_snapshot
                    attempt.terminal_snapshot = None
                    should_refresh_account = terminal_snapshot.status == "succeeded"
                else:
                    attempt.snapshot = replace(
                        attempt.snapshot,
                        status="failed",
                        auth_url=None,
                        verification_url=None,
                        user_code=None,
                        error="Codex login ended because cancellation was interrupted.",
                        completed_at=_now_iso(),
                    )
                    should_discard_client = True
                    if attempt.waiter is not None and not attempt.waiter.done():
                        waiter = attempt.waiter
                        waiter.cancel()
                if self._active_login_id == login_id:
                    self._active_login_id = None

            if waiter is not None:
                with suppress(asyncio.CancelledError):
                    await waiter
            if should_discard_client:
                await self._discard_client(attempt.client)
            elif should_refresh_account:
                with suppress(CodexRuntimeError):
                    await self._refresh_account()
            raise
        except (TimeoutError, TransportClosedError) as exc:
            await self._discard_client(attempt.client)
            failed_snapshot = replace(
                attempt.snapshot,
                status="failed",
                auth_url=None,
                verification_url=None,
                user_code=None,
                error="Codex login ended because the runtime did not respond.",
                completed_at=_now_iso(),
            )
            async with self._login_lock:
                attempt.snapshot = failed_snapshot
                attempt.terminal_snapshot = None
                if self._active_login_id == login_id:
                    self._active_login_id = None
            if attempt.waiter is not None and not attempt.waiter.done():
                attempt.waiter.cancel()
                with suppress(asyncio.CancelledError):
                    await attempt.waiter
            raise CodexRuntimeUnavailableError(
                "Codex runtime login cancellation did not complete."
            ) from exc
        except Exception as exc:
            completed_snapshot: CodexLoginSnapshot | None = None
            async with self._login_lock:
                terminal_snapshot = attempt.terminal_snapshot
                if terminal_snapshot is not None:
                    attempt.snapshot = terminal_snapshot
                    attempt.terminal_snapshot = None
                    if self._active_login_id == login_id:
                        self._active_login_id = None
                    completed_snapshot = terminal_snapshot
                else:
                    attempt.snapshot = replace(
                        attempt.snapshot,
                        status="pending",
                        error="Unable to cancel Codex login; the attempt may still be active.",
                    )
            if completed_snapshot is not None:
                if completed_snapshot.status == "succeeded":
                    with suppress(CodexRuntimeError):
                        await self._refresh_account()
                return completed_snapshot
            logger.warning("Codex login cancellation failed (%s)", type(exc).__name__)
            raise CodexRuntimeError("Unable to cancel Codex login.") from exc

        waiter: asyncio.Task[None] | None = None
        should_refresh_account = False
        async with self._login_lock:
            terminal_snapshot = attempt.terminal_snapshot
            if terminal_snapshot is not None:
                result_snapshot = terminal_snapshot
                attempt.snapshot = terminal_snapshot
                attempt.terminal_snapshot = None
                should_refresh_account = terminal_snapshot.status == "succeeded"
            else:
                result_snapshot = replace(
                    attempt.snapshot,
                    status="canceled",
                    auth_url=None,
                    verification_url=None,
                    user_code=None,
                    error=None,
                    completed_at=_now_iso(),
                )
                attempt.snapshot = result_snapshot
                if attempt.waiter is not None and not attempt.waiter.done():
                    waiter = attempt.waiter
                    waiter.cancel()
            if self._active_login_id == login_id:
                self._active_login_id = None

        if waiter is not None:
            with suppress(asyncio.CancelledError):
                await waiter
        if should_refresh_account:
            with suppress(CodexRuntimeError):
                await self._refresh_account()
        return result_snapshot

    async def logout(self) -> CodexAccountSnapshot:
        """Cancel interactive login, clear Codex auth, and return account state."""
        async with self._auth_operation_lock:
            async with self._login_lock:
                active_login_id = self._active_login_id
            if active_login_id is not None:
                await self._cancel_login(active_login_id)

            client = await self._ensure_started()
            try:
                async with asyncio.timeout(_RUNTIME_CONTROL_TIMEOUT_SECONDS):
                    await client.logout()
            except (TimeoutError, TransportClosedError) as exc:
                await self._discard_client(client)
                raise CodexRuntimeUnavailableError(
                    "Codex runtime logout did not complete."
                ) from exc
            except Exception as exc:
                logger.warning("Codex logout failed (%s)", type(exc).__name__)
                raise CodexRuntimeError("Unable to log out of Codex.") from exc

            self._default_model = None
            self._account_snapshot = CodexAccountSnapshot(
                runtime_status="ready",
                authenticated=False,
                requires_openai_auth=True,
                account_type=None,
                email=None,
                plan_type=None,
            )
            return self._account_snapshot

    async def run_turn(
        self,
        *,
        prompt: str,
        model: str | None = None,
        developer_instructions: str | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: int = 180,
    ) -> CodexTurnResult:
        """Run one provider turn on the runtime's owning event loop."""
        current_loop = asyncio.get_running_loop()
        owner_loop = self._owner_loop
        if owner_loop is not None and owner_loop is not current_loop:
            if owner_loop.is_closed():
                await self._rebind_after_closed_owner(current_loop)
            else:
                owner_future = asyncio.run_coroutine_threadsafe(
                    self._run_turn_on_owner(
                        prompt=prompt,
                        model=model,
                        developer_instructions=developer_instructions,
                        reasoning_effort=reasoning_effort,
                        timeout_seconds=timeout_seconds,
                    ),
                    owner_loop,
                )
                try:
                    return await asyncio.wrap_future(owner_future)
                except asyncio.CancelledError:
                    owner_future.cancel()
                    raise

        return await self._run_turn_on_owner(
            prompt=prompt,
            model=model,
            developer_instructions=developer_instructions,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
        )

    async def _rebind_after_closed_owner(
        self,
        current_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Retire loop-bound state after a short-lived owner loop has closed."""
        stale_client = self._client
        self._client = None
        if stale_client is not None:
            await self._safe_close_client(stale_client)

        self._lifecycle_lock = asyncio.Lock()
        self._account_lock = asyncio.Lock()
        self._auth_operation_lock = asyncio.Lock()
        self._login_lock = asyncio.Lock()
        self._logins.clear()
        self._active_login_id = None
        self._default_model = None
        self._next_start_attempt = 0.0
        self._account_snapshot = CodexAccountSnapshot(
            runtime_status="stopped",
            authenticated=False,
            requires_openai_auth=None,
            account_type=None,
            email=None,
            plan_type=None,
        )
        self._owner_loop = current_loop

    async def _run_turn_on_owner(
        self,
        *,
        prompt: str,
        model: str | None,
        developer_instructions: str | None,
        reasoning_effort: str | None,
        timeout_seconds: int,
    ) -> CodexTurnResult:
        """Run one stateless, tool-disabled turn on the owning event loop."""
        client = await self._ensure_started()
        if not self.is_authenticated:
            snapshot = await self.refresh_account()
            if not snapshot.authenticated:
                raise CodexNotAuthenticatedError(
                    "Codex is not authenticated. Connect a ChatGPT account first."
                )

        cwd = self.isolated_cwd
        if cwd is None:
            raise CodexRuntimeUnavailableError("Codex isolated working directory is unavailable")

        effort = ReasoningEffort(reasoning_effort) if reasoning_effort else None
        combined_instructions = self._compose_developer_instructions(developer_instructions)
        started_at = time.perf_counter()
        turn: Any | None = None

        try:
            async with asyncio.timeout(timeout_seconds):
                thread = await client.thread_start(
                    approval_mode=ApprovalMode.deny_all,
                    base_instructions=_PROVIDER_INSTRUCTIONS,
                    config=_provider_config(),
                    cwd=str(cwd),
                    developer_instructions=combined_instructions,
                    ephemeral=True,
                    model=model,
                    sandbox=Sandbox.read_only,
                )
                turn = await thread.turn(
                    prompt,
                    approval_mode=ApprovalMode.deny_all,
                    cwd=str(cwd),
                    effort=effort,
                    model=model,
                    sandbox=Sandbox.read_only,
                )
                result = await turn.run()
        except TimeoutError:
            if turn is not None:
                await self._interrupt_turn(turn)
            await self._discard_client(client)
            raise
        except asyncio.CancelledError:
            if turn is not None:
                await self._interrupt_turn(turn)
            await self._discard_client(client)
            raise
        except TransportClosedError as exc:
            await self._discard_client(client)
            raise CodexRuntimeUnavailableError(
                "Codex runtime connection closed."
            ) from exc

        turn_status = _enum_value(result.status)
        if turn_status != "completed":
            raise CodexRuntimeError(
                f"Codex turn did not complete successfully (status={turn_status or 'unknown'})"
            )
        if not result.final_response:
            raise CodexRuntimeError("Codex turn completed without a final response")

        usage = getattr(result, "usage", None)
        last_usage = getattr(usage, "last", None)
        duration_ms = result.duration_ms
        if duration_ms is None:
            duration_ms = int((time.perf_counter() - started_at) * 1000)

        return CodexTurnResult(
            content=result.final_response,
            model=model or self._default_model or "codex-default",
            turn_id=result.id,
            duration_ms=duration_ms,
            finish_reason=turn_status,
            input_tokens=int(getattr(last_usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(last_usage, "output_tokens", 0) or 0),
            total_tokens=int(getattr(last_usage, "total_tokens", 0) or 0),
            cached_input_tokens=int(getattr(last_usage, "cached_input_tokens", 0) or 0),
            reasoning_output_tokens=int(
                getattr(last_usage, "reasoning_output_tokens", 0) or 0
            ),
        )

    async def _ensure_started(self) -> Any:
        await self.start()
        if self._client is None:
            message = self._account_snapshot.error_message or "Codex runtime is unavailable"
            raise CodexRuntimeUnavailableError(message)
        return self._client

    async def _discard_client(self, client: Any | None) -> None:
        """Clear one dead client so a later request can restart the runtime."""
        if client is None:
            return
        async with self._lifecycle_lock:
            if self._client is not client:
                return
            self._client = None
            self._default_model = None
            self._next_start_attempt = 0.0
            self._account_snapshot = CodexAccountSnapshot(
                runtime_status="stopped",
                authenticated=False,
                requires_openai_auth=None,
                account_type=None,
                email=None,
                plan_type=None,
                error_code="transport_closed",
                error_message="Codex runtime connection closed; the next request will restart it.",
            )
            await self._safe_close_client(client)

    async def _finish_pending_logins_for_shutdown(self) -> None:
        """Cancel waiter tasks and redact pending login ceremonies on shutdown."""
        waiters: list[asyncio.Task[None]] = []
        async with self._login_lock:
            for attempt in self._logins.values():
                if attempt.snapshot.status not in {"pending", "canceling"}:
                    continue
                attempt.snapshot = replace(
                    attempt.snapshot,
                    status="canceled",
                    auth_url=None,
                    verification_url=None,
                    user_code=None,
                    error=None,
                    completed_at=_now_iso(),
                )
                attempt.terminal_snapshot = None
                if attempt.waiter is not None and not attempt.waiter.done():
                    attempt.waiter.cancel()
                    waiters.append(attempt.waiter)
            self._active_login_id = None

        for waiter in waiters:
            with suppress(asyncio.CancelledError):
                await waiter

    @staticmethod
    async def _safe_close_client(client: Any) -> None:
        """Close an SDK client without allowing shutdown to hang indefinitely."""
        task = asyncio.create_task(client.close())
        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                timeout=_CLIENT_CLOSE_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError:
            task.cancel()
            with suppress(BaseException):
                await task
            raise
        except Exception as exc:
            task.cancel()
            with suppress(BaseException):
                await task
            logger.warning("Codex client cleanup failed (%s)", type(exc).__name__)

    async def _abandon_login_start(
        self,
        task: asyncio.Task[Any],
        client: Any,
    ) -> None:
        """Retire a client whose blocking login-start request was abandoned."""
        task.cancel()
        await self._discard_client(client)
        with suppress(BaseException):
            await task

    def _ensure_isolated_cwd(self) -> None:
        if self._configured_cwd is not None:
            self._configured_cwd.mkdir(parents=True, exist_ok=True)
            return
        if self._temporary_cwd is None:
            self._temporary_cwd = tempfile.TemporaryDirectory(
                prefix="inqulume-codex-provider-"
            )

    def _cleanup_temporary_cwd(self) -> None:
        if self._temporary_cwd is None:
            return
        self._temporary_cwd.cleanup()
        self._temporary_cwd = None

    def _create_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        cwd = self.isolated_cwd
        return AsyncCodex(
            CodexConfig(
                config_overrides=_provider_process_overrides(),
                cwd=str(cwd) if cwd is not None else None,
                client_name="inqulume_studio",
                client_title="Inqulume Studio",
            )
        )

    def _snapshot_from_account(self, response: Any) -> CodexAccountSnapshot:
        account_wrapper = getattr(response, "account", None)
        account = getattr(account_wrapper, "root", account_wrapper)
        account_type = getattr(account, "type", None) if account is not None else None
        return CodexAccountSnapshot(
            runtime_status="ready",
            authenticated=account is not None,
            requires_openai_auth=bool(getattr(response, "requires_openai_auth", False)),
            account_type=_enum_value(account_type),
            email=getattr(account, "email", None) if account is not None else None,
            plan_type=_enum_value(getattr(account, "plan_type", None))
            if account is not None
            else None,
        )

    @staticmethod
    async def _validate_effective_security(client: Any) -> None:
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
        if not _effective_security_config_is_safe(effective_config):
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

    async def _refresh_default_model(self, client: Any) -> None:
        try:
            async with asyncio.timeout(_RUNTIME_CONTROL_TIMEOUT_SECONDS):
                response = await client.models()
        except (TimeoutError, TransportClosedError):
            raise
        except Exception as exc:
            logger.debug(
                "Codex default-model discovery failed (%s)",
                type(exc).__name__,
            )
            return
        for model in getattr(response, "data", []):
            if bool(getattr(model, "is_default", False)):
                self._default_model = str(model.model)
                return

    async def _start_login(self, flow: str) -> CodexLoginSnapshot:
        async with self._auth_operation_lock:
            client = await self._ensure_started()
            async with self._login_lock:
                if self._active_login_id is not None:
                    active_attempt = self._logins.get(self._active_login_id)
                    if active_attempt is not None and active_attempt.snapshot.status in {
                        "pending",
                        "canceling",
                    }:
                        raise CodexLoginConflictError(
                            f"Codex login {self._active_login_id} is already active"
                        )

            login_task = asyncio.create_task(
                client.login_chatgpt()
                if flow == "browser"
                else client.login_chatgpt_device_code()
            )
            try:
                handle = await asyncio.wait_for(
                    asyncio.shield(login_task),
                    timeout=_RUNTIME_CONTROL_TIMEOUT_SECONDS,
                )
            except asyncio.CancelledError:
                await self._abandon_login_start(login_task, client)
                raise
            except TimeoutError as exc:
                await self._abandon_login_start(login_task, client)
                logger.warning("Codex %s login startup timed out", flow)
                raise CodexRuntimeUnavailableError(
                    "Codex runtime login startup did not complete."
                ) from exc
            except TransportClosedError as exc:
                await self._discard_client(client)
                raise CodexRuntimeUnavailableError(
                    "Codex runtime connection closed."
                ) from exc
            except Exception as exc:
                logger.warning(
                    "Codex %s login startup failed (%s)",
                    flow,
                    type(exc).__name__,
                )
                raise CodexRuntimeError(f"Unable to start Codex {flow} login.") from exc

            snapshot = CodexLoginSnapshot(
                login_id=str(handle.login_id),
                flow=flow,
                status="pending",
                auth_url=getattr(handle, "auth_url", None),
                verification_url=getattr(handle, "verification_url", None),
                user_code=getattr(handle, "user_code", None),
                error=None,
                created_at=_now_iso(),
                completed_at=None,
            )
            attempt = _LoginAttempt(
                snapshot=snapshot,
                handle=handle,
                client=client,
            )
            try:
                async with self._login_lock:
                    self._logins[snapshot.login_id] = attempt
                    self._active_login_id = snapshot.login_id
                    attempt.waiter = asyncio.create_task(
                        self._wait_for_login(snapshot.login_id),
                        name=f"codex-login-{snapshot.login_id}",
                    )
            except asyncio.CancelledError:
                await self._abandon_login_start(login_task, client)
                raise
            return snapshot

    async def _wait_for_login(self, login_id: str) -> None:
        attempt = self._logins[login_id]
        should_refresh_account = False
        try:
            completed = await attempt.handle.wait()
            success = bool(getattr(completed, "success", False))
            terminal_snapshot = replace(
                attempt.snapshot,
                status="succeeded" if success else "failed",
                auth_url=None,
                verification_url=None,
                user_code=None,
                error=None if success else "Codex login failed.",
                completed_at=_now_iso(),
            )
        except asyncio.CancelledError:
            raise
        except TransportClosedError:
            await self._discard_client(attempt.client)
            logger.warning("Codex login waiter lost the runtime connection")
            terminal_snapshot = replace(
                attempt.snapshot,
                status="failed",
                auth_url=None,
                verification_url=None,
                user_code=None,
                error="Codex login ended because the runtime connection closed.",
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.warning("Codex login waiter failed (%s)", type(exc).__name__)
            terminal_snapshot = replace(
                attempt.snapshot,
                status="failed",
                auth_url=None,
                verification_url=None,
                user_code=None,
                error="Codex login failed.",
                completed_at=_now_iso(),
            )

        async with self._login_lock:
            if attempt.snapshot.status == "canceling":
                attempt.terminal_snapshot = terminal_snapshot
                return
            attempt.snapshot = terminal_snapshot
            attempt.terminal_snapshot = None
            if self._active_login_id == login_id:
                self._active_login_id = None
            should_refresh_account = terminal_snapshot.status == "succeeded"

        if should_refresh_account:
            async with self._auth_operation_lock:
                with suppress(CodexRuntimeError):
                    await self._refresh_account()

    @staticmethod
    def _compose_developer_instructions(value: str | None) -> str:
        if not value:
            return _PROVIDER_INSTRUCTIONS
        return f"{value.rstrip()}\n\n{_PROVIDER_INSTRUCTIONS}"

    @staticmethod
    async def _interrupt_turn(turn: Any) -> None:
        task = asyncio.create_task(turn.interrupt())
        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                timeout=_TURN_INTERRUPT_TIMEOUT_SECONDS,
            )
        except BaseException:
            task.cancel()
            with suppress(BaseException):
                await task


_shared_runtime: CodexRuntime | None = None


def get_shared_codex_runtime() -> CodexRuntime:
    """Return the process-shared Codex runtime used by auth and transports."""
    global _shared_runtime
    if _shared_runtime is None:
        _shared_runtime = CodexRuntime()
    return _shared_runtime


__all__ = [
    "CodexAccountSnapshot",
    "CodexLoginConflictError",
    "CodexLoginNotFoundError",
    "CodexLoginSnapshot",
    "CodexNotAuthenticatedError",
    "CodexRuntime",
    "CodexRuntimeError",
    "CodexRuntimeUnavailableError",
    "CodexTurnResult",
    "get_shared_codex_runtime",
]
