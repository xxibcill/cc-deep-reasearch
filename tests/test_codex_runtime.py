"""Tests for the shared Codex app-server runtime boundary."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from openai_codex import ApprovalMode, Sandbox, TransportClosedError

from cc_deep_research.llm.codex_runtime import (
    CodexLoginConflictError,
    CodexNotAuthenticatedError,
    CodexRuntime,
    CodexRuntimeError,
    CodexRuntimeUnavailableError,
    _effective_security_config_is_safe,
    _provider_config,
    _provider_process_overrides,
)


def _account_response(*, authenticated: bool) -> SimpleNamespace:
    account = None
    if authenticated:
        account = SimpleNamespace(
            root=SimpleNamespace(
                type="chatgpt",
                email="operator@example.com",
                plan_type=SimpleNamespace(value="plus"),
            )
        )
    return SimpleNamespace(
        account=account,
        requires_openai_auth=True,
    )


def _turn_result(*, status: str = "completed") -> SimpleNamespace:
    return SimpleNamespace(
        id="turn-123",
        status=SimpleNamespace(value=status),
        duration_ms=125,
        final_response="Codex response",
        usage=SimpleNamespace(
            last=SimpleNamespace(
                input_tokens=12,
                output_tokens=7,
                total_tokens=19,
                cached_input_tokens=3,
                reasoning_output_tokens=2,
            )
        ),
    )


class FakeTurn:
    def __init__(
        self,
        *,
        result: SimpleNamespace | None = None,
        block: bool = False,
    ) -> None:
        self.result = result or _turn_result()
        self.block = block
        self.interrupted = False

    async def run(self) -> SimpleNamespace:
        if self.block:
            await asyncio.Event().wait()
        return self.result

    async def interrupt(self) -> None:
        self.interrupted = True


class FakeThread:
    def __init__(self, turn: FakeTurn) -> None:
        self._turn = turn
        self.turn_calls: list[tuple[str, dict[str, Any]]] = []

    async def turn(self, prompt: str, **kwargs: Any) -> FakeTurn:
        self.turn_calls.append((prompt, kwargs))
        return self._turn


class FakeLoginHandle:
    def __init__(self, *, flow: str) -> None:
        self.login_id = f"{flow}-login"
        self.auth_url = "https://example.test/browser" if flow == "browser" else None
        self.verification_url = (
            "https://example.test/device" if flow == "device_code" else None
        )
        self.user_code = "ABCD-1234" if flow == "device_code" else None
        self.completed: asyncio.Future[SimpleNamespace] = asyncio.get_running_loop().create_future()
        self.cancelled = False

    async def wait(self) -> SimpleNamespace:
        return await self.completed

    async def cancel(self) -> None:
        self.cancelled = True


class FakeCodexClient:
    def __init__(
        self,
        *,
        authenticated: bool,
        turn: FakeTurn | None = None,
    ) -> None:
        self.account_response = _account_response(authenticated=authenticated)
        self.thread = FakeThread(turn or FakeTurn())
        self.thread_start_calls: list[dict[str, Any]] = []
        self.account_calls: list[bool] = []
        self.closed = False
        self.logged_out = False
        self.browser_handle: FakeLoginHandle | None = None
        self.device_handle: FakeLoginHandle | None = None

    async def account(self, *, refresh_token: bool = False) -> SimpleNamespace:
        self.account_calls.append(refresh_token)
        return self.account_response

    async def models(self) -> SimpleNamespace:
        return SimpleNamespace(
            data=[
                SimpleNamespace(model="gpt-5.6-sol", is_default=True),
                SimpleNamespace(model="gpt-5.4", is_default=False),
            ]
        )

    async def thread_start(self, **kwargs: Any) -> FakeThread:
        self.thread_start_calls.append(kwargs)
        return self.thread

    async def login_chatgpt(self) -> FakeLoginHandle:
        self.browser_handle = FakeLoginHandle(flow="browser")
        return self.browser_handle

    async def login_chatgpt_device_code(self) -> FakeLoginHandle:
        self.device_handle = FakeLoginHandle(flow="device_code")
        return self.device_handle

    async def logout(self) -> None:
        self.logged_out = True

    async def close(self) -> None:
        self.closed = True


class DeadTurnCodexClient(FakeCodexClient):
    async def thread_start(self, **kwargs: Any) -> FakeThread:
        raise TransportClosedError("secret app-server stderr")


class BlockingAccountCodexClient(FakeCodexClient):
    def __init__(self) -> None:
        super().__init__(authenticated=True)
        self.account_started = asyncio.Event()

    async def account(self, *, refresh_token: bool = False) -> SimpleNamespace:
        self.account_calls.append(refresh_token)
        self.account_started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class BlockingThreadStartCodexClient(FakeCodexClient):
    async def thread_start(self, **kwargs: Any) -> FakeThread:
        self.thread_start_calls.append(kwargs)
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class BlockingModelsCodexClient(FakeCodexClient):
    async def models(self) -> SimpleNamespace:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class RacingAccountCodexClient(FakeCodexClient):
    def __init__(self) -> None:
        super().__init__(authenticated=True)
        self.block_refresh = False
        self.refresh_started = asyncio.Event()
        self.release_refresh = asyncio.Event()

    async def account(self, *, refresh_token: bool = False) -> SimpleNamespace:
        self.account_calls.append(refresh_token)
        if self.block_refresh:
            self.refresh_started.set()
            await self.release_refresh.wait()
        return _account_response(authenticated=True)


class LoopRecordingCodexClient(FakeCodexClient):
    def __init__(self) -> None:
        super().__init__(authenticated=True)
        self.thread_start_loop: asyncio.AbstractEventLoop | None = None

    async def thread_start(self, **kwargs: Any) -> FakeThread:
        self.thread_start_loop = asyncio.get_running_loop()
        return await super().thread_start(**kwargs)


class BlockingLoginCodexClient(FakeCodexClient):
    def __init__(self) -> None:
        super().__init__(authenticated=False)
        self.login_started = asyncio.Event()

    async def login_chatgpt(self) -> FakeLoginHandle:
        self.login_started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_run_turn_uses_isolated_tool_disabled_configuration(tmp_path) -> None:
    client = FakeCodexClient(authenticated=True)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )

    result = await runtime.run_turn(
        prompt="Answer this",
        developer_instructions="Return concise JSON.",
        reasoning_effort="high",
        timeout_seconds=30,
    )

    assert result.content == "Codex response"
    assert result.model == "gpt-5.6-sol"
    assert result.input_tokens == 12
    assert result.output_tokens == 7
    assert result.cached_input_tokens == 3

    start_kwargs = client.thread_start_calls[0]
    assert start_kwargs["ephemeral"] is True
    assert start_kwargs["approval_mode"] == ApprovalMode.deny_all
    assert start_kwargs["sandbox"] == Sandbox.read_only
    assert start_kwargs["cwd"] == str(tmp_path / "isolated")
    assert start_kwargs["model"] is None
    assert start_kwargs["base_instructions"].startswith(
        "Operate only as a text-generation provider."
    )
    assert start_kwargs["config"] == {
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
    assert "Return concise JSON." in start_kwargs["developer_instructions"]
    assert "Do not invoke shell commands" in start_kwargs["developer_instructions"]

    prompt, turn_kwargs = client.thread.turn_calls[0]
    assert prompt == "Answer this"
    assert turn_kwargs["approval_mode"] == ApprovalMode.deny_all
    assert turn_kwargs["sandbox"] == Sandbox.read_only
    assert turn_kwargs["effort"].value == "high"

    await runtime.close()
    assert client.closed is True


@pytest.mark.asyncio
async def test_unauthenticated_runtime_rejects_turn_before_thread_start(tmp_path) -> None:
    client = FakeCodexClient(authenticated=False)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )

    with pytest.raises(CodexNotAuthenticatedError):
        await runtime.run_turn(prompt="Do work")

    assert client.thread_start_calls == []
    await runtime.close()


@pytest.mark.asyncio
async def test_browser_login_is_single_flight_and_redacts_terminal_snapshot(tmp_path) -> None:
    client = FakeCodexClient(authenticated=False)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )

    pending = await runtime.login_browser()
    assert pending.status == "pending"
    assert pending.auth_url == "https://example.test/browser"

    with pytest.raises(CodexLoginConflictError):
        await runtime.login_device_code()

    assert client.browser_handle is not None
    client.account_response = _account_response(authenticated=True)
    client.browser_handle.completed.set_result(SimpleNamespace(success=True, error=None))
    waiter = runtime._logins[pending.login_id].waiter
    assert waiter is not None
    await waiter

    completed = runtime.get_login(pending.login_id)
    assert completed.status == "succeeded"
    assert completed.auth_url is None
    assert completed.verification_url is None
    assert completed.user_code is None
    assert completed.error is None
    assert runtime.is_authenticated is True
    await runtime.close()


@pytest.mark.asyncio
async def test_cancel_login_redacts_device_code(tmp_path) -> None:
    client = FakeCodexClient(authenticated=False)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )

    pending = await runtime.login_device_code()
    canceled = await runtime.cancel_login(pending.login_id)

    assert canceled.status == "canceled"
    assert canceled.verification_url is None
    assert canceled.user_code is None
    assert client.device_handle is not None
    assert client.device_handle.cancelled is True
    await runtime.close()


@pytest.mark.asyncio
async def test_cancelled_cancellation_releases_active_login(tmp_path) -> None:
    first_client = FakeCodexClient(authenticated=False)
    second_client = FakeCodexClient(authenticated=False)
    clients = iter((first_client, second_client))
    runtime = CodexRuntime(
        client_factory=lambda: next(clients),
        isolated_cwd=tmp_path / "isolated",
    )
    pending = await runtime.login_browser()
    active = await runtime.get_active_login()
    assert active is not None
    assert active.login_id == pending.login_id
    assert first_client.browser_handle is not None
    cancel_started = asyncio.Event()

    async def blocking_cancel() -> None:
        cancel_started.set()
        await asyncio.Event().wait()

    first_client.browser_handle.cancel = AsyncMock(  # type: ignore[method-assign]
        side_effect=blocking_cancel
    )
    cancel_task = asyncio.create_task(runtime.cancel_login(pending.login_id))
    await cancel_started.wait()
    cancel_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await cancel_task

    terminal = runtime.get_login(pending.login_id)
    assert terminal.status == "failed"
    assert terminal.auth_url is None
    assert await runtime.get_active_login() is None
    assert first_client.closed is True

    replacement = await runtime.login_device_code()
    assert replacement.status == "pending"
    assert replacement.login_id == "device_code-login"
    await runtime.close()


@pytest.mark.asyncio
async def test_turn_timeout_interrupts_active_codex_turn(tmp_path) -> None:
    turn = FakeTurn(block=True)
    client = FakeCodexClient(authenticated=True, turn=turn)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )

    with pytest.raises(TimeoutError):
        await runtime.run_turn(prompt="Never finish", timeout_seconds=0)

    assert turn.interrupted is True
    assert client.closed is True
    assert runtime.runtime_status == "stopped"
    await runtime.close()


@pytest.mark.asyncio
async def test_turn_timeout_covers_thread_start(tmp_path) -> None:
    client = BlockingThreadStartCodexClient(authenticated=True)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )

    with pytest.raises(TimeoutError):
        await runtime.run_turn(prompt="Never start", timeout_seconds=0)

    assert client.closed is True
    assert runtime.runtime_status == "stopped"
    await runtime.close()


@pytest.mark.asyncio
async def test_worker_loop_turn_runs_on_runtime_owner_loop(tmp_path) -> None:
    client = LoopRecordingCodexClient()
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    await runtime.start()
    owner_loop = asyncio.get_running_loop()

    result = await asyncio.to_thread(
        lambda: asyncio.run(runtime.run_turn(prompt="Cross-loop request"))
    )

    assert result.content == "Codex response"
    assert client.thread_start_loop is owner_loop
    await runtime.close()


@pytest.mark.asyncio
async def test_closed_short_lived_owner_loop_restarts_cleanly(tmp_path) -> None:
    first_client = FakeCodexClient(authenticated=True)
    second_client = FakeCodexClient(authenticated=True)
    clients = iter([first_client, second_client])
    runtime = CodexRuntime(
        client_factory=lambda: next(clients),
        isolated_cwd=tmp_path / "isolated",
    )

    first_result = await asyncio.to_thread(
        lambda: asyncio.run(runtime.run_turn(prompt="First loop"))
    )

    async def run_again_and_close() -> str:
        result = await runtime.run_turn(prompt="Second loop")
        await runtime.close()
        return result.content

    second_content = await asyncio.to_thread(lambda: asyncio.run(run_again_and_close()))

    assert first_result.content == "Codex response"
    assert second_content == "Codex response"
    assert first_client.closed is True
    assert second_client.thread_start_calls
    assert second_client.closed is True


@pytest.mark.asyncio
async def test_non_completed_turn_is_rejected_even_with_final_text(tmp_path) -> None:
    turn = FakeTurn(result=_turn_result(status="interrupted"))
    client = FakeCodexClient(authenticated=True, turn=turn)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )

    with pytest.raises(CodexRuntimeError, match="did not complete successfully"):
        await runtime.run_turn(prompt="Interrupted")

    await runtime.close()


@pytest.mark.asyncio
async def test_start_failure_snapshot_does_not_expose_exception_message(tmp_path) -> None:
    def fail_factory() -> Any:
        raise RuntimeError("secret child process details")

    runtime = CodexRuntime(
        client_factory=fail_factory,
        isolated_cwd=tmp_path / "isolated",
    )

    await runtime.start()

    snapshot = runtime.account_snapshot
    assert snapshot.runtime_status == "error"
    assert snapshot.error_code == "RuntimeError"
    assert snapshot.error_message == "Codex runtime could not be started."
    assert "secret" not in (snapshot.error_message or "")
    assert runtime.can_attempt_start is False
    runtime._next_start_attempt = 0
    assert runtime.can_attempt_start is True


@pytest.mark.asyncio
async def test_cancel_failure_keeps_login_pollable(tmp_path) -> None:
    client = FakeCodexClient(authenticated=False)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    pending = await runtime.login_browser()
    assert client.browser_handle is not None
    client.browser_handle.cancel = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("secret cancellation detail")
    )

    with pytest.raises(CodexRuntimeError, match="Unable to cancel"):
        await runtime.cancel_login(pending.login_id)

    retryable = runtime.get_login(pending.login_id)
    assert retryable.status == "pending"
    assert "secret" not in (retryable.error or "")
    waiter = runtime._logins[pending.login_id].waiter
    assert waiter is not None
    assert waiter.done() is False

    client.browser_handle.completed.set_result(SimpleNamespace(success=False))
    await waiter
    assert runtime.get_login(pending.login_id).status == "failed"
    await runtime.close()


@pytest.mark.asyncio
async def test_cancel_and_logout_are_single_flight(tmp_path) -> None:
    client = FakeCodexClient(authenticated=False)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    pending = await runtime.login_browser()
    assert client.browser_handle is not None
    cancel_started = asyncio.Event()
    release_cancel = asyncio.Event()

    async def blocking_cancel() -> None:
        cancel_started.set()
        await release_cancel.wait()

    client.browser_handle.cancel = AsyncMock(  # type: ignore[method-assign]
        side_effect=blocking_cancel
    )
    cancel_task = asyncio.create_task(runtime.cancel_login(pending.login_id))
    await cancel_started.wait()
    logout_task = asyncio.create_task(runtime.logout())
    await asyncio.sleep(0)

    assert client.browser_handle.cancel.await_count == 1
    assert client.logged_out is False

    release_cancel.set()
    canceled, account = await asyncio.gather(cancel_task, logout_task)

    assert canceled.status == "canceled"
    assert account.authenticated is False
    assert client.browser_handle.cancel.await_count == 1
    assert client.logged_out is True
    await runtime.close()


@pytest.mark.asyncio
async def test_cancel_returns_login_completion_that_won_the_race(tmp_path) -> None:
    client = FakeCodexClient(authenticated=False)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    pending = await runtime.login_browser()
    assert client.browser_handle is not None
    cancel_started = asyncio.Event()
    release_cancel = asyncio.Event()

    async def blocking_cancel() -> None:
        cancel_started.set()
        await release_cancel.wait()

    client.browser_handle.cancel = AsyncMock(  # type: ignore[method-assign]
        side_effect=blocking_cancel
    )
    cancel_task = asyncio.create_task(runtime.cancel_login(pending.login_id))
    await cancel_started.wait()
    client.account_response = _account_response(authenticated=True)
    client.browser_handle.completed.set_result(SimpleNamespace(success=True))
    waiter = runtime._logins[pending.login_id].waiter
    assert waiter is not None
    await waiter
    release_cancel.set()

    completed = await cancel_task

    assert completed.status == "succeeded"
    assert runtime.is_authenticated is True
    await runtime.close()


@pytest.mark.asyncio
async def test_logout_cannot_be_overwritten_by_stale_account_refresh(tmp_path) -> None:
    client = RacingAccountCodexClient()
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    await runtime.start()
    client.block_refresh = True

    refresh_task = asyncio.create_task(runtime.refresh_account())
    await client.refresh_started.wait()
    logout_task = asyncio.create_task(runtime.logout())
    await asyncio.sleep(0)

    assert client.logged_out is False

    client.release_refresh.set()
    refreshed, logged_out = await asyncio.gather(refresh_task, logout_task)

    assert refreshed.authenticated is True
    assert logged_out.authenticated is False
    assert runtime.is_authenticated is False
    assert runtime.default_model is None
    await runtime.close()


@pytest.mark.asyncio
async def test_account_refresh_timeout_discards_client(
    tmp_path,
    monkeypatch,
) -> None:
    client = RacingAccountCodexClient()
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    await runtime.start()
    client.block_refresh = True
    monkeypatch.setattr(
        "cc_deep_research.llm.codex_runtime._RUNTIME_CONTROL_TIMEOUT_SECONDS",
        0.01,
    )

    with pytest.raises(CodexRuntimeUnavailableError, match="did not complete"):
        await runtime.refresh_account()

    assert client.closed is True
    assert runtime.runtime_status == "stopped"
    assert runtime._client is None
    await runtime.close()


@pytest.mark.asyncio
async def test_login_start_timeout_discards_client(
    tmp_path,
    monkeypatch,
) -> None:
    client = BlockingLoginCodexClient()
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    await runtime.start()
    monkeypatch.setattr(
        "cc_deep_research.llm.codex_runtime._RUNTIME_CONTROL_TIMEOUT_SECONDS",
        0.01,
    )

    with pytest.raises(CodexRuntimeUnavailableError, match="did not complete"):
        await runtime.login_browser()

    assert client.login_started.is_set()
    assert client.closed is True
    assert runtime.runtime_status == "stopped"
    assert runtime._client is None
    await runtime.close()


@pytest.mark.asyncio
async def test_stale_login_failure_does_not_discard_restarted_client(tmp_path) -> None:
    stale_client = FakeCodexClient(authenticated=False)
    healthy_client = FakeCodexClient(authenticated=True)
    runtime = CodexRuntime(
        client_factory=lambda: stale_client,
        isolated_cwd=tmp_path / "isolated",
    )
    pending = await runtime.login_browser()
    assert stale_client.browser_handle is not None

    stale_client.browser_handle.completed.set_exception(
        TransportClosedError("stale client closed")
    )
    runtime._client = healthy_client
    runtime._account_snapshot = runtime._snapshot_from_account(
        _account_response(authenticated=True)
    )
    waiter = runtime._logins[pending.login_id].waiter
    assert waiter is not None
    await waiter

    assert runtime._client is healthy_client
    assert healthy_client.closed is False
    assert runtime.get_login(pending.login_id).status == "failed"
    await runtime.close()


@pytest.mark.asyncio
async def test_dead_transport_is_discarded_and_next_turn_restarts(tmp_path) -> None:
    dead_client = DeadTurnCodexClient(authenticated=True)
    healthy_client = FakeCodexClient(authenticated=True)
    clients = iter([dead_client, healthy_client])
    runtime = CodexRuntime(
        client_factory=lambda: next(clients),
        isolated_cwd=tmp_path / "isolated",
    )

    with pytest.raises(CodexRuntimeUnavailableError, match="connection closed"):
        await runtime.run_turn(prompt="First request")

    assert dead_client.closed is True
    assert runtime.runtime_status == "stopped"

    result = await runtime.run_turn(prompt="Second request")

    assert result.content == "Codex response"
    assert healthy_client.thread_start_calls
    await runtime.close()


@pytest.mark.asyncio
async def test_canceled_start_closes_unassigned_client(tmp_path) -> None:
    client = BlockingAccountCodexClient()
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    start_task = asyncio.create_task(runtime.start())
    await client.account_started.wait()

    start_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await start_task

    assert client.closed is True
    assert runtime.runtime_status == "stopped"
    assert runtime._client is None


@pytest.mark.asyncio
async def test_default_model_discovery_is_bounded(
    tmp_path,
    monkeypatch,
) -> None:
    client = BlockingModelsCodexClient(authenticated=True)
    runtime = CodexRuntime(
        client_factory=lambda: client,
        isolated_cwd=tmp_path / "isolated",
    )
    monkeypatch.setattr(
        "cc_deep_research.llm.codex_runtime._RUNTIME_CONTROL_TIMEOUT_SECONDS",
        0.01,
    )

    await asyncio.wait_for(runtime.start(), timeout=1)

    assert runtime.runtime_status == "error"
    assert runtime.default_model is None
    assert client.closed is True
    assert runtime._client is None
    await runtime.close()


def test_effective_security_config_fails_closed() -> None:
    safe_config = _provider_config()
    safe_config["mcp_servers"] = {
        "docs": {
            "enabled": False,
            "command": "codex-provider-disabled",
        }
    }

    assert _effective_security_config_is_safe(safe_config) is True
    assert _effective_security_config_is_safe({**safe_config, "tools": {}}) is True

    unsafe_otel = {**safe_config, "otel": {**safe_config["otel"], "log_user_prompt": True}}
    unsafe_mcp = {
        **safe_config,
        "mcp_servers": {"docs": {"enabled": True, "command": "docs-server"}},
    }
    unsafe_features = {
        **safe_config,
        "features": {**safe_config["features"], "shell_tool": True},
    }
    unsafe_view_image = {
        **safe_config,
        "tools": {**safe_config["tools"], "view_image": True},
    }
    unsafe_tool_web_search = {
        **safe_config,
        "tools": {**safe_config["tools"], "web_search": True},
    }
    missing_tools = {key: value for key, value in safe_config.items() if key != "tools"}

    assert _effective_security_config_is_safe(unsafe_otel) is False
    assert _effective_security_config_is_safe(unsafe_mcp) is False
    assert _effective_security_config_is_safe(unsafe_features) is False
    assert _effective_security_config_is_safe(unsafe_view_image) is False
    assert _effective_security_config_is_safe(unsafe_tool_web_search) is False
    assert _effective_security_config_is_safe(missing_tools) is False


def test_process_overrides_disable_named_mcp_servers(tmp_path, monkeypatch) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        """
[mcp_servers.docs]
command = "docs-server"

[mcp_servers.server_with_underscores]
url = "https://example.test/mcp"
""".strip()
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    overrides = _provider_process_overrides()

    assert "features.hooks=false" in overrides
    assert "features.plugins=false" in overrides
    assert "features.unified_exec=false" in overrides
    assert 'otel.exporter="none"' in overrides
    assert "otel.log_user_prompt=false" in overrides
    assert 'otel.metrics_exporter="none"' in overrides
    assert 'otel.trace_exporter="none"' in overrides
    assert "notify=[]" in overrides
    assert 'shell_environment_policy.inherit="none"' in overrides
    assert (
        'mcp_servers.docs={enabled=false,command="codex-provider-disabled"}'
        in overrides
    )
    assert (
        'mcp_servers.server_with_underscores='
        '{enabled=false,url="http://127.0.0.1:9/codex-provider-disabled"}'
        in overrides
    )
