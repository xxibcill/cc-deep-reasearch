"""Shared lifecycle and authentication boundary for the Codex app-server."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import tempfile
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import Any

from openai_codex import AsyncCodex, CodexConfig, TransportClosedError

from cc_deep_research.llm.codex_login import CodexLoginManager
from cc_deep_research.llm.codex_security import (
    provider_process_overrides as _provider_process_overrides,
)
from cc_deep_research.llm.codex_security_probe import validate_effective_security
from cc_deep_research.llm.codex_turn import execute_codex_turn
from cc_deep_research.llm.codex_types import (
    CodexAccountSnapshot,
    CodexLoginConflictError,
    CodexLoginFlow,
    CodexLoginNotFoundError,
    CodexLoginSnapshot,
    CodexLoginStatus,
    CodexNotAuthenticatedError,
    CodexRuntimeError,
    CodexRuntimeStatus,
    CodexRuntimeUnavailableError,
    CodexTurnResult,
)

logger = logging.getLogger(__name__)

_CLIENT_CLOSE_TIMEOUT_SECONDS = 5.0
_RUNTIME_CONTROL_TIMEOUT_SECONDS = 30.0
_START_RETRY_DELAY_SECONDS = 5.0


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    raw_value = getattr(value, "value", value)
    return str(raw_value)


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
        self._turn_lock = asyncio.Lock()
        self._state_guard = threading.Lock()
        self._rebind_future: concurrent.futures.Future[None] | None = None
        self._turn_generation = 0
        self._scope_generations: dict[str, int] = {}
        self._closing = False
        self._active_turn_task: asyncio.Task[Any] | None = None
        self._active_turn_scope: str | None = None
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
        self._login_manager = CodexLoginManager(
            ensure_started=self._ensure_started,
            discard_client=self._discard_client,
            refresh_account=self.refresh_account,
            refresh_account_unlocked=self._refresh_account,
            control_timeout_seconds=lambda: _RUNTIME_CONTROL_TIMEOUT_SECONDS,
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
    def runtime_status(self) -> CodexRuntimeStatus:
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
        if self._owner_loop is None or (self._owner_loop.is_closed() and self._client is None):
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
                        await validate_effective_security(client)
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
            await self._begin_turn_barrier()
            try:
                active_login_id = await self._login_manager.active_login_id()
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

                await self._login_manager.finish_pending_for_shutdown()
            finally:
                self._end_turn_barrier()

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
        async with self._auth_operation_lock:
            return await self._login_manager.start("browser")

    async def login_device_code(self) -> CodexLoginSnapshot:
        """Start managed device-code ChatGPT login."""
        async with self._auth_operation_lock:
            return await self._login_manager.start("device_code")

    async def get_active_login(self) -> CodexLoginSnapshot | None:
        """Return the safe snapshot for the active login ceremony, if any."""
        return await self._login_manager.get_active()

    def get_login(self, login_id: str) -> CodexLoginSnapshot:
        """Return a safe snapshot for a known login attempt."""
        return self._login_manager.get(login_id)

    async def cancel_login(self, login_id: str) -> CodexLoginSnapshot:
        """Cancel a pending login and return its terminal snapshot."""
        async with self._auth_operation_lock:
            return await self._cancel_login(login_id)

    async def _cancel_login(self, login_id: str) -> CodexLoginSnapshot:
        """Cancel one login while the caller owns the auth-operation lock."""
        return await self._login_manager.cancel(login_id)

    async def logout(self) -> CodexAccountSnapshot:
        """Cancel interactive login, clear Codex auth, and return account state."""
        async with self._auth_operation_lock:
            await self._begin_turn_barrier()
            try:
                active_login_id = await self._login_manager.active_login_id()
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
            finally:
                self._end_turn_barrier()

    async def run_turn(
        self,
        *,
        prompt: str,
        model: str | None = None,
        developer_instructions: str | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: int = 180,
        scope_id: str | None = None,
    ) -> CodexTurnResult:
        """Run one provider turn on the runtime's owning event loop."""
        current_loop = asyncio.get_running_loop()
        with self._state_guard:
            if self._closing:
                raise CodexRuntimeUnavailableError("Codex runtime lifecycle is changing.")
            if self._owner_loop is None:
                self._owner_loop = current_loop
            turn_generation = self._turn_generation
            scope_generation = self._scope_generations.get(scope_id, 0) if scope_id else 0
        deadline = time.monotonic() + timeout_seconds

        while True:
            with self._state_guard:
                owner_loop = self._owner_loop
            assert owner_loop is not None
            if owner_loop is not current_loop:
                if owner_loop.is_closed() or not owner_loop.is_running():
                    await self._ensure_rebound_after_closed_owner(
                        current_loop,
                        stale_owner_loop=owner_loop,
                    )
                    continue
                turn_coroutine = self._run_turn_on_owner(
                    prompt=prompt,
                    model=model,
                    developer_instructions=developer_instructions,
                    reasoning_effort=reasoning_effort,
                    timeout_seconds=timeout_seconds,
                    deadline=deadline,
                    turn_generation=turn_generation,
                    scope_id=scope_id,
                    scope_generation=scope_generation,
                )
                try:
                    owner_future = asyncio.run_coroutine_threadsafe(
                        turn_coroutine,
                        owner_loop,
                    )
                except RuntimeError as exc:
                    turn_coroutine.close()
                    if await self._wait_for_owner_loop_shutdown(owner_loop, deadline=deadline):
                        await self._ensure_rebound_after_closed_owner(
                            current_loop,
                            stale_owner_loop=owner_loop,
                        )
                        continue
                    raise CodexRuntimeUnavailableError(
                        "Codex runtime owner loop stopped accepting work."
                    ) from exc
                try:
                    return await asyncio.wrap_future(owner_future)
                except asyncio.CancelledError:
                    current_task = asyncio.current_task()
                    if current_task is not None and current_task.cancelling():
                        owner_future.cancel()
                        raise
                    self._assert_turn_generation(
                        turn_generation,
                        scope_id=scope_id,
                        scope_generation=scope_generation,
                    )
                    if await self._wait_for_owner_loop_shutdown(owner_loop, deadline=deadline):
                        await self._ensure_rebound_after_closed_owner(
                            current_loop,
                            stale_owner_loop=owner_loop,
                        )
                        continue
                    raise

            return await self._run_turn_on_owner(
                prompt=prompt,
                model=model,
                developer_instructions=developer_instructions,
                reasoning_effort=reasoning_effort,
                timeout_seconds=timeout_seconds,
                deadline=deadline,
                turn_generation=turn_generation,
                scope_id=scope_id,
                scope_generation=scope_generation,
            )

    def request_cancel_scope(self, scope_id: str) -> None:
        """Cancel active and invalidate queued turns for one workflow scope."""
        if not scope_id:
            return
        with self._state_guard:
            self._scope_generations[scope_id] = self._scope_generations.get(scope_id, 0) + 1
            active_turn_task = (
                self._active_turn_task if self._active_turn_scope == scope_id else None
            )
            owner_loop = self._owner_loop
        if active_turn_task is None or active_turn_task.done():
            return
        if owner_loop is not None and not owner_loop.is_closed():
            owner_loop.call_soon_threadsafe(active_turn_task.cancel)
        else:
            active_turn_task.cancel()

    async def _ensure_rebound_after_closed_owner(
        self,
        current_loop: asyncio.AbstractEventLoop,
        *,
        stale_owner_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Allow one caller to rebuild loop-bound state after owner shutdown."""
        with self._state_guard:
            if self._owner_loop is not stale_owner_loop:
                return
            rebind_future = self._rebind_future
            is_rebind_owner = rebind_future is None or rebind_future.done()
            if is_rebind_owner:
                rebind_future = concurrent.futures.Future()
                self._rebind_future = rebind_future

        assert rebind_future is not None
        if not is_rebind_owner:
            await asyncio.wrap_future(rebind_future)
            return

        try:
            await self._rebind_after_closed_owner(current_loop)
        except BaseException as exc:
            rebind_future.set_exception(exc)
            rebind_future.exception()
            raise
        else:
            rebind_future.set_result(None)

    @staticmethod
    async def _wait_for_owner_loop_shutdown(
        owner_loop: asyncio.AbstractEventLoop,
        *,
        deadline: float,
    ) -> bool:
        """Briefly wait for a transient owner loop to finish asyncio shutdown."""
        wait_deadline = min(deadline, time.monotonic() + 0.1)
        while owner_loop.is_running() and time.monotonic() < wait_deadline:
            await asyncio.sleep(0.001)
        return owner_loop.is_closed() or not owner_loop.is_running()

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
        self._turn_lock = asyncio.Lock()
        self._login_manager.reset_after_owner_shutdown()
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
        with self._state_guard:
            self._owner_loop = current_loop

    async def _run_turn_on_owner(
        self,
        *,
        prompt: str,
        model: str | None,
        developer_instructions: str | None,
        reasoning_effort: str | None,
        timeout_seconds: int,
        deadline: float,
        turn_generation: int,
        scope_id: str | None,
        scope_generation: int,
    ) -> CodexTurnResult:
        """Run one stateless, tool-disabled turn on the owning event loop."""
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            raise TimeoutError

        async with asyncio.timeout(remaining_seconds):
            async with self._turn_lock:
                self._assert_turn_generation(
                    turn_generation,
                    scope_id=scope_id,
                    scope_generation=scope_generation,
                )
                active_task = asyncio.current_task()
                assert active_task is not None
                with self._state_guard:
                    self._active_turn_task = active_task
                    self._active_turn_scope = scope_id
                try:
                    self._assert_turn_generation(
                        turn_generation,
                        scope_id=scope_id,
                        scope_generation=scope_generation,
                    )
                    return await self._run_serialized_turn(
                        prompt=prompt,
                        model=model,
                        developer_instructions=developer_instructions,
                        reasoning_effort=reasoning_effort,
                        timeout_seconds=timeout_seconds,
                    )
                finally:
                    with self._state_guard:
                        if self._active_turn_task is active_task:
                            self._active_turn_task = None
                            self._active_turn_scope = None

    def _assert_turn_generation(
        self,
        turn_generation: int,
        *,
        scope_id: str | None,
        scope_generation: int,
    ) -> None:
        with self._state_guard:
            lifecycle_is_current = (
                not self._closing and turn_generation == self._turn_generation
            )
            scope_is_current = scope_id is None or scope_generation == self._scope_generations.get(
                scope_id, 0
            )
        if not lifecycle_is_current:
            raise CodexRuntimeUnavailableError(
                "Codex runtime lifecycle changed while the request was queued."
            )
        if not scope_is_current:
            raise asyncio.CancelledError

    async def _begin_turn_barrier(self) -> None:
        """Cancel the active turn and drain callers from the previous generation."""
        with self._state_guard:
            self._closing = True
            self._turn_generation += 1
            active_turn_task = self._active_turn_task
        current_task = asyncio.current_task()
        if active_turn_task is not None and active_turn_task is not current_task:
            active_turn_task.cancel()
            with suppress(BaseException):
                await active_turn_task
        async with self._turn_lock:
            pass

    def _end_turn_barrier(self) -> None:
        with self._state_guard:
            self._closing = False

    async def _run_serialized_turn(
        self,
        *,
        prompt: str,
        model: str | None,
        developer_instructions: str | None,
        reasoning_effort: str | None,
        timeout_seconds: int,
    ) -> CodexTurnResult:
        """Run one turn while exclusively owning the shared client."""
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

        try:
            return await execute_codex_turn(
                client,
                cwd=cwd,
                prompt=prompt,
                model=model,
                default_model=self._default_model,
                developer_instructions=developer_instructions,
                reasoning_effort=reasoning_effort,
                timeout_seconds=timeout_seconds,
            )
        except (TimeoutError, asyncio.CancelledError):
            await self._discard_client(client)
            raise
        except TransportClosedError as exc:
            await self._discard_client(client)
            raise CodexRuntimeUnavailableError("Codex runtime connection closed.") from exc

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

    def _ensure_isolated_cwd(self) -> None:
        if self._configured_cwd is not None:
            self._configured_cwd.mkdir(parents=True, exist_ok=True)
            return
        if self._temporary_cwd is None:
            self._temporary_cwd = tempfile.TemporaryDirectory(prefix="inqulume-codex-provider-")

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
        normalized_account_type = _enum_value(account_type)
        return CodexAccountSnapshot(
            runtime_status="ready",
            authenticated=normalized_account_type == "chatgpt",
            requires_openai_auth=bool(getattr(response, "requires_openai_auth", False)),
            account_type=normalized_account_type,
            email=getattr(account, "email", None) if account is not None else None,
            plan_type=_enum_value(getattr(account, "plan_type", None))
            if account is not None
            else None,
        )

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
    "CodexLoginFlow",
    "CodexLoginNotFoundError",
    "CodexLoginSnapshot",
    "CodexLoginStatus",
    "CodexNotAuthenticatedError",
    "CodexRuntime",
    "CodexRuntimeError",
    "CodexRuntimeStatus",
    "CodexRuntimeUnavailableError",
    "CodexTurnResult",
    "get_shared_codex_runtime",
]
