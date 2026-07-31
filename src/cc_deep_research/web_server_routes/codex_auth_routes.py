"""Local-only HTTP routes for the shared Codex authentication runtime."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable, Sequence
from ipaddress import ip_address
from typing import cast
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from cc_deep_research.llm.codex_runtime import (
    CodexAccountSnapshot,
    CodexLoginConflictError,
    CodexLoginFlow,
    CodexLoginNotFoundError,
    CodexLoginSnapshot,
    CodexLoginStatus,
    CodexRuntime,
    CodexRuntimeError,
    CodexRuntimeStatus,
    CodexRuntimeUnavailableError,
)

logger = logging.getLogger(__name__)

DEFAULT_DASHBOARD_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://[::1]:3000",
)
_CORS_ORIGINS_ENV = "CORS_ALLOWED_ORIGINS"


class CodexAccountResponse(BaseModel):
    """Token-free public account state returned to the dashboard."""

    model_config = ConfigDict(frozen=True)

    runtime_status: CodexRuntimeStatus
    authenticated: bool
    requires_openai_auth: bool | None
    account_type: str | None
    email: str | None
    plan_type: str | None
    error_code: str | None = None
    error_message: str | None = None


class CodexLoginResponse(BaseModel):
    """Public state for one managed ChatGPT login attempt."""

    model_config = ConfigDict(frozen=True)

    login_id: str
    flow: CodexLoginFlow
    status: CodexLoginStatus
    auth_url: str | None
    verification_url: str | None
    user_code: str | None
    error: str | None
    created_at: str
    completed_at: str | None


class CodexAuthErrorResponse(BaseModel):
    """Stable error envelope that never includes SDK exception details."""

    model_config = ConfigDict(frozen=True)

    code: str
    error: str


def _is_loopback_host(host: str | None) -> bool:
    """Return whether *host* is a localhost name or loopback IP literal."""
    if host is None:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def _normalize_http_origin(value: str, *, allow_path: bool = False) -> str | None:
    """Return a canonical HTTP origin, rejecting ambiguous URL forms."""
    if not value or "," in value:
        return None

    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or parsed.hostname is None:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if not allow_path and (parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        return None

    try:
        port = parsed.port
    except ValueError:
        return None

    host = parsed.hostname.lower()
    rendered_host = f"[{host}]" if ":" in host else host
    default_port = 80 if scheme == "http" else 443
    port_suffix = f":{port}" if port is not None and port != default_port else ""
    return f"{scheme}://{rendered_host}{port_suffix}"


def resolve_dashboard_cors_origins(
    configured_origins: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Resolve and validate the exact browser origins trusted by the dashboard."""
    if configured_origins is None:
        configured_value = os.environ.get(_CORS_ORIGINS_ENV)
        configured_origins = (
            tuple(configured_value.split(","))
            if configured_value is not None
            else DEFAULT_DASHBOARD_CORS_ORIGINS
        )

    normalized_origins: list[str] = []
    for configured_origin in configured_origins:
        origin = configured_origin.strip()
        if origin == "*":
            raise ValueError(
                f"{_CORS_ORIGINS_ENV} must contain explicit origins; wildcard '*' is not allowed."
            )
        normalized = _normalize_http_origin(origin)
        if normalized is None:
            raise ValueError(f"Invalid dashboard CORS origin: {configured_origin!r}")
        if normalized not in normalized_origins:
            normalized_origins.append(normalized)

    if not normalized_origins:
        raise ValueError("At least one dashboard CORS origin must be configured.")
    return tuple(normalized_origins)


def _has_allowed_dashboard_origin(request: Request) -> bool:
    """Require browser metadata to match the configured dashboard allowlist."""
    allowed_origins = frozenset(
        cast(
            "tuple[str, ...]",
            getattr(
                request.app.state,
                "dashboard_cors_origins",
                DEFAULT_DASHBOARD_CORS_ORIGINS,
            ),
        )
    )
    origin = request.headers.get("origin")
    if origin is not None:
        normalized_origin = _normalize_http_origin(origin)
        return normalized_origin is not None and normalized_origin in allowed_origins

    referer = request.headers.get("referer")
    if referer is not None:
        normalized_referer = _normalize_http_origin(referer, allow_path=True)
        return normalized_referer is not None and normalized_referer in allowed_origins

    return True


def _require_local_codex_request(request: Request) -> None:
    """Allow Codex account mutations only from a loopback peer and origin."""
    client_host = request.client.host if request.client is not None else None
    if not _is_loopback_host(client_host) or not _has_allowed_dashboard_origin(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Codex authentication is available only to the local dashboard.",
        )


def _get_codex_runtime(request: Request) -> CodexRuntime:
    """Return the shared runtime attached to the FastAPI application."""
    dashboard_runtime = getattr(request.app.state, "dashboard_runtime", None)
    runtime = getattr(dashboard_runtime, "codex_runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Codex runtime is unavailable.",
        )
    return cast(CodexRuntime, runtime)


def _account_response(snapshot: CodexAccountSnapshot) -> CodexAccountResponse:
    """Map a runtime account snapshot through an explicit public allowlist."""
    return CodexAccountResponse(
        runtime_status=snapshot.runtime_status,
        authenticated=snapshot.authenticated,
        requires_openai_auth=snapshot.requires_openai_auth,
        account_type=snapshot.account_type,
        email=snapshot.email,
        plan_type=snapshot.plan_type,
        error_code=snapshot.error_code,
        error_message=snapshot.error_message,
    )


def _login_response(snapshot: CodexLoginSnapshot) -> CodexLoginResponse:
    """Map a runtime login snapshot through an explicit public allowlist."""
    return CodexLoginResponse(
        login_id=snapshot.login_id,
        flow=snapshot.flow,
        status=snapshot.status,
        auth_url=snapshot.auth_url,
        verification_url=snapshot.verification_url,
        user_code=snapshot.user_code,
        error=snapshot.error,
        created_at=snapshot.created_at,
        completed_at=snapshot.completed_at,
    )


def _error_response(
    *,
    action: str,
    error: Exception,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    """Log only the exception type and return a stable, token-free error."""
    logger.warning("Codex %s failed with %s", action, type(error).__name__)
    payload = CodexAuthErrorResponse(code=code, error=message)
    return JSONResponse(content=payload.model_dump(mode="json"), status_code=status_code)


async def _start_login(
    login: Callable[[], Awaitable[CodexLoginSnapshot]],
    *,
    action: str,
) -> CodexLoginResponse | JSONResponse:
    """Start one login flow with the shared public exception mapping."""
    try:
        snapshot = await login()
    except CodexLoginConflictError as error:
        return _error_response(
            action=action,
            error=error,
            status_code=status.HTTP_409_CONFLICT,
            code="codex_login_in_progress",
            message="A Codex login is already in progress.",
        )
    except CodexRuntimeUnavailableError as error:
        return _error_response(
            action=action,
            error=error,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="codex_runtime_unavailable",
            message="Codex runtime is unavailable.",
        )
    except CodexRuntimeError as error:
        return _error_response(
            action=action,
            error=error,
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="codex_login_failed",
            message="Codex login could not be started.",
        )
    return _login_response(snapshot)


def register_codex_auth_routes(
    app: FastAPI,
    *,
    allowed_origins: Sequence[str] | None = None,
) -> None:
    """Register local-only Codex account and managed login routes."""
    app.state.dashboard_cors_origins = resolve_dashboard_cors_origins(allowed_origins)
    router = APIRouter(
        prefix="/api/llm/codex",
        tags=["codex-auth"],
        dependencies=[Depends(_require_local_codex_request)],
    )

    @router.get("/account", response_model=CodexAccountResponse)
    async def get_codex_account(request: Request) -> CodexAccountResponse | JSONResponse:
        runtime = _get_codex_runtime(request)
        try:
            snapshot = await runtime.refresh_account(refresh_token=False)
        except CodexRuntimeUnavailableError as error:
            return _error_response(
                action="account refresh",
                error=error,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="codex_runtime_unavailable",
                message="Codex runtime is unavailable.",
            )
        except CodexRuntimeError as error:
            return _error_response(
                action="account refresh",
                error=error,
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="codex_account_read_failed",
                message="Codex account state could not be read.",
            )
        return _account_response(snapshot)

    @router.post(
        "/login/browser",
        response_model=CodexLoginResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_browser_login(request: Request) -> CodexLoginResponse | JSONResponse:
        runtime = _get_codex_runtime(request)
        return await _start_login(runtime.login_browser, action="browser login")

    @router.post(
        "/login/device-code",
        response_model=CodexLoginResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_device_code_login(request: Request) -> CodexLoginResponse | JSONResponse:
        runtime = _get_codex_runtime(request)
        return await _start_login(runtime.login_device_code, action="device-code login")

    @router.get("/login/active", response_model=CodexLoginResponse | None)
    async def get_active_login_attempt(
        request: Request,
    ) -> CodexLoginResponse | None:
        runtime = _get_codex_runtime(request)
        snapshot = await runtime.get_active_login()
        return _login_response(snapshot) if snapshot is not None else None

    @router.get("/login/{login_id}", response_model=CodexLoginResponse)
    async def get_login_attempt(
        login_id: str,
        request: Request,
    ) -> CodexLoginResponse | JSONResponse:
        runtime = _get_codex_runtime(request)
        try:
            snapshot = runtime.get_login(login_id)
        except CodexLoginNotFoundError as error:
            return _error_response(
                action="login lookup",
                error=error,
                status_code=status.HTTP_404_NOT_FOUND,
                code="codex_login_not_found",
                message="Codex login attempt was not found.",
            )
        return _login_response(snapshot)

    @router.delete("/login/{login_id}", response_model=CodexLoginResponse)
    async def cancel_login_attempt(
        login_id: str,
        request: Request,
    ) -> CodexLoginResponse | JSONResponse:
        runtime = _get_codex_runtime(request)
        try:
            snapshot = await runtime.cancel_login(login_id)
        except CodexLoginNotFoundError as error:
            return _error_response(
                action="login cancellation",
                error=error,
                status_code=status.HTTP_404_NOT_FOUND,
                code="codex_login_not_found",
                message="Codex login attempt was not found.",
            )
        except CodexRuntimeUnavailableError as error:
            return _error_response(
                action="login cancellation",
                error=error,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="codex_runtime_unavailable",
                message="Codex runtime is unavailable.",
            )
        except CodexRuntimeError as error:
            return _error_response(
                action="login cancellation",
                error=error,
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="codex_login_cancel_failed",
                message="Codex login could not be cancelled.",
            )
        return _login_response(snapshot)

    @router.post("/logout", response_model=CodexAccountResponse)
    async def logout_codex_account(request: Request) -> CodexAccountResponse | JSONResponse:
        runtime = _get_codex_runtime(request)
        try:
            snapshot = await runtime.logout()
        except CodexRuntimeUnavailableError as error:
            return _error_response(
                action="logout",
                error=error,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="codex_runtime_unavailable",
                message="Codex runtime is unavailable.",
            )
        except CodexRuntimeError as error:
            return _error_response(
                action="logout",
                error=error,
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="codex_logout_failed",
                message="Codex logout failed.",
            )
        return _account_response(snapshot)

    app.include_router(router)


__all__ = [
    "CodexAccountResponse",
    "CodexAuthErrorResponse",
    "CodexLoginResponse",
    "register_codex_auth_routes",
]
