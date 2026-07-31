"""Interactive ChatGPT login state machine for the Codex provider runtime."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from openai_codex import TransportClosedError

from cc_deep_research.llm.codex_types import (
    CodexAccountSnapshot,
    CodexLoginConflictError,
    CodexLoginFlow,
    CodexLoginNotFoundError,
    CodexLoginSnapshot,
    CodexRuntimeError,
    CodexRuntimeUnavailableError,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _LoginAttempt:
    snapshot: CodexLoginSnapshot
    handle: Any
    client: Any
    waiter: asyncio.Task[None] | None = None
    terminal_snapshot: CodexLoginSnapshot | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class CodexLoginManager:
    """Own login attempts while the runtime owns process and account lifecycle."""

    def __init__(
        self,
        *,
        ensure_started: Callable[[], Awaitable[Any]],
        discard_client: Callable[[Any | None], Awaitable[None]],
        refresh_account: Callable[[], Awaitable[CodexAccountSnapshot]],
        refresh_account_unlocked: Callable[[], Awaitable[CodexAccountSnapshot]],
        control_timeout_seconds: Callable[[], float],
    ) -> None:
        self._ensure_started = ensure_started
        self._discard_client = discard_client
        self._refresh_account = refresh_account
        self._refresh_account_unlocked = refresh_account_unlocked
        self._control_timeout_seconds = control_timeout_seconds
        self._lock = asyncio.Lock()
        self._attempts: dict[str, _LoginAttempt] = {}
        self._active_login_id: str | None = None

    async def active_login_id(self) -> str | None:
        """Return the active login identifier, if one is still tracked."""
        async with self._lock:
            return self._active_login_id

    async def get_active(self) -> CodexLoginSnapshot | None:
        """Return the safe snapshot for the active login ceremony, if any."""
        async with self._lock:
            if self._active_login_id is None:
                return None
            attempt = self._attempts.get(self._active_login_id)
            if attempt is None:
                return None
            return attempt.terminal_snapshot or attempt.snapshot

    def get(self, login_id: str) -> CodexLoginSnapshot:
        """Return a safe snapshot for a known login attempt."""
        attempt = self._attempts.get(login_id)
        if attempt is None:
            raise CodexLoginNotFoundError(f"Unknown Codex login: {login_id}")
        return attempt.snapshot

    async def start(self, flow: CodexLoginFlow) -> CodexLoginSnapshot:
        """Start one browser or device-code login while the caller serializes auth."""
        client = await self._ensure_started()
        async with self._lock:
            if self._active_login_id is not None:
                active_attempt = self._attempts.get(self._active_login_id)
                if active_attempt is not None and active_attempt.snapshot.status in {
                    "pending",
                    "canceling",
                }:
                    raise CodexLoginConflictError(
                        f"Codex login {self._active_login_id} is already active"
                    )

        login_task = asyncio.create_task(
            client.login_chatgpt() if flow == "browser" else client.login_chatgpt_device_code()
        )
        try:
            handle = await asyncio.wait_for(
                asyncio.shield(login_task),
                timeout=self._control_timeout_seconds(),
            )
        except asyncio.CancelledError:
            await self._abandon_start(login_task, client)
            raise
        except TimeoutError as exc:
            await self._abandon_start(login_task, client)
            logger.warning("Codex %s login startup timed out", flow)
            raise CodexRuntimeUnavailableError(
                "Codex runtime login startup did not complete."
            ) from exc
        except TransportClosedError as exc:
            await self._discard_client(client)
            raise CodexRuntimeUnavailableError("Codex runtime connection closed.") from exc
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
        attempt = _LoginAttempt(snapshot=snapshot, handle=handle, client=client)
        try:
            async with self._lock:
                self._attempts[snapshot.login_id] = attempt
                self._active_login_id = snapshot.login_id
                attempt.waiter = asyncio.create_task(
                    self._wait_for_login(snapshot.login_id),
                    name=f"codex-login-{snapshot.login_id}",
                )
        except asyncio.CancelledError:
            await self._abandon_start(login_task, client)
            raise
        return snapshot

    async def cancel(self, login_id: str) -> CodexLoginSnapshot:
        """Cancel one login while the caller serializes auth operations."""
        async with self._lock:
            attempt = self._attempts.get(login_id)
            if attempt is None:
                raise CodexLoginNotFoundError(f"Unknown Codex login: {login_id}")
            if attempt.snapshot.status not in {"pending", "canceling"}:
                return attempt.snapshot
            attempt.snapshot = replace(attempt.snapshot, status="canceling")

        try:
            async with asyncio.timeout(self._control_timeout_seconds()):
                await attempt.handle.cancel()
        except asyncio.CancelledError:
            waiter: asyncio.Task[None] | None = None
            should_discard_client = False
            should_refresh_account = False
            async with self._lock:
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
                    await self._refresh_account_unlocked()
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
            async with self._lock:
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
            async with self._lock:
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
                        await self._refresh_account_unlocked()
                return completed_snapshot
            logger.warning("Codex login cancellation failed (%s)", type(exc).__name__)
            raise CodexRuntimeError("Unable to cancel Codex login.") from exc

        waiter = None
        should_refresh_account = False
        async with self._lock:
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
                await self._refresh_account_unlocked()
        return result_snapshot

    async def finish_pending_for_shutdown(self) -> None:
        """Cancel waiter tasks and redact pending ceremonies on shutdown."""
        waiters: list[asyncio.Task[None]] = []
        async with self._lock:
            for attempt in self._attempts.values():
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

    def reset_after_owner_shutdown(self) -> None:
        """Reset loop-bound state after the previous event loop has stopped."""
        self._lock = asyncio.Lock()
        self._attempts.clear()
        self._active_login_id = None

    async def _abandon_start(self, task: asyncio.Task[Any], client: Any) -> None:
        task.cancel()
        await self._discard_client(client)
        with suppress(BaseException):
            await task

    async def _wait_for_login(self, login_id: str) -> None:
        attempt = self._attempts[login_id]
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

        async with self._lock:
            if attempt.snapshot.status == "canceling":
                attempt.terminal_snapshot = terminal_snapshot
                return
            attempt.snapshot = terminal_snapshot
            attempt.terminal_snapshot = None
            if self._active_login_id == login_id:
                self._active_login_id = None
            should_refresh_account = terminal_snapshot.status == "succeeded"

        if should_refresh_account:
            with suppress(CodexRuntimeError):
                await self._refresh_account()
