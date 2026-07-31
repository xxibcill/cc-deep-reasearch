"""Tests for the local-only Codex authentication HTTP API."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cc_deep_research.llm.codex_runtime import (
    CodexAccountSnapshot,
    CodexLoginConflictError,
    CodexLoginNotFoundError,
    CodexLoginSnapshot,
    CodexRuntimeUnavailableError,
)
from cc_deep_research.web_server import create_app
from cc_deep_research.web_server_routes.codex_auth_routes import (
    register_codex_auth_routes,
    resolve_dashboard_cors_origins,
)


def _account_snapshot(*, authenticated: bool = True) -> CodexAccountSnapshot:
    return CodexAccountSnapshot(
        runtime_status="ready",
        authenticated=authenticated,
        requires_openai_auth=True,
        account_type="chatgpt" if authenticated else None,
        email="operator@example.com" if authenticated else None,
        plan_type="plus" if authenticated else None,
    )


def _login_snapshot(
    *,
    flow: str = "browser",
    status: str = "pending",
) -> CodexLoginSnapshot:
    return CodexLoginSnapshot(
        login_id="login-123",
        flow=flow,
        status=status,
        auth_url="https://chatgpt.com/auth" if flow == "browser" else None,
        verification_url=(
            "https://auth.openai.com/codex/device" if flow == "device_code" else None
        ),
        user_code="ABCD-1234" if flow == "device_code" else None,
        error=None,
        created_at="2026-07-31T12:00:00+00:00",
        completed_at=None,
    )


class FakeCodexRuntime:
    """Small runtime double that exposes only the route-facing contract."""

    def __init__(self) -> None:
        self.account = _account_snapshot()
        self.browser_login = _login_snapshot()
        self.device_login = replace(
            _login_snapshot(flow="device_code"),
            login_id="device-123",
        )
        self.logins = {
            self.browser_login.login_id: self.browser_login,
            self.device_login.login_id: self.device_login,
        }
        self.active_login_id: str | None = None
        self.refresh_calls = 0
        self.browser_calls = 0
        self.device_calls = 0
        self.cancel_calls: list[str] = []
        self.logout_calls = 0
        self.refresh_error: Exception | None = None
        self.browser_error: Exception | None = None

    async def refresh_account(self, *, refresh_token: bool = False) -> CodexAccountSnapshot:
        assert refresh_token is False
        self.refresh_calls += 1
        if self.refresh_error is not None:
            raise self.refresh_error
        return self.account

    async def login_browser(self) -> CodexLoginSnapshot:
        self.browser_calls += 1
        if self.browser_error is not None:
            raise self.browser_error
        self.logins[self.browser_login.login_id] = self.browser_login
        self.active_login_id = self.browser_login.login_id
        return self.browser_login

    async def login_device_code(self) -> CodexLoginSnapshot:
        self.device_calls += 1
        self.logins[self.device_login.login_id] = self.device_login
        self.active_login_id = self.device_login.login_id
        return self.device_login

    async def get_active_login(self) -> CodexLoginSnapshot | None:
        if self.active_login_id is None:
            return None
        return self.logins[self.active_login_id]

    def get_login(self, login_id: str) -> CodexLoginSnapshot:
        try:
            return self.logins[login_id]
        except KeyError as error:
            raise CodexLoginNotFoundError("private runtime detail") from error

    async def cancel_login(self, login_id: str) -> CodexLoginSnapshot:
        self.cancel_calls.append(login_id)
        snapshot = self.get_login(login_id)
        cancelled = replace(
            snapshot,
            status="canceled",
            auth_url=None,
            verification_url=None,
            user_code=None,
            completed_at="2026-07-31T12:01:00+00:00",
        )
        self.logins[login_id] = cancelled
        if self.active_login_id == login_id:
            self.active_login_id = None
        return cancelled

    async def logout(self) -> CodexAccountSnapshot:
        self.logout_calls += 1
        self.active_login_id = None
        self.account = _account_snapshot(authenticated=False)
        return self.account


@pytest.fixture
def runtime() -> FakeCodexRuntime:
    return FakeCodexRuntime()


def _build_client(
    runtime: FakeCodexRuntime,
    *,
    client_host: str = "127.0.0.1",
    headers: dict[str, str] | None = None,
) -> TestClient:
    app = FastAPI()
    app.state.dashboard_runtime = SimpleNamespace(codex_runtime=runtime)
    register_codex_auth_routes(app)
    return TestClient(
        app,
        client=(client_host, 50000),
        headers=headers or {"Origin": "http://localhost:3000"},
    )


def test_account_returns_explicit_token_free_shape(runtime: FakeCodexRuntime) -> None:
    runtime.account = SimpleNamespace(
        runtime_status=runtime.account.runtime_status,
        authenticated=runtime.account.authenticated,
        requires_openai_auth=runtime.account.requires_openai_auth,
        account_type=runtime.account.account_type,
        email=runtime.account.email,
        plan_type=runtime.account.plan_type,
        error_code=runtime.account.error_code,
        error_message=runtime.account.error_message,
        access_token="secret-access-token",
        refresh_token="secret-refresh-token",
    )
    client = _build_client(runtime)

    response = client.get("/api/llm/codex/account")

    assert response.status_code == 200
    assert response.json() == {
        "runtime_status": "ready",
        "authenticated": True,
        "requires_openai_auth": True,
        "account_type": "chatgpt",
        "email": "operator@example.com",
        "plan_type": "plus",
        "error_code": None,
        "error_message": None,
    }
    assert "secret-access-token" not in response.text
    assert "secret-refresh-token" not in response.text


def test_create_app_registers_codex_auth_routes(runtime: FakeCodexRuntime) -> None:
    app = create_app(codex_runtime=runtime)  # type: ignore[arg-type]
    client = TestClient(
        app,
        client=("127.0.0.1", 50000),
        headers={"Origin": "http://localhost:3000"},
    )

    response = client.get("/api/llm/codex/account")

    assert response.status_code == 200
    assert response.json()["account_type"] == "chatgpt"


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3001",
        "http://localhost.attacker.invalid:3000",
    ],
)
def test_auth_routes_reject_foreign_or_lookalike_localhost_origins(
    runtime: FakeCodexRuntime,
    origin: str,
) -> None:
    app = FastAPI()
    app.state.dashboard_runtime = SimpleNamespace(codex_runtime=runtime)
    register_codex_auth_routes(
        app,
        allowed_origins=("http://localhost:3000",),
    )
    client = TestClient(
        app,
        client=("127.0.0.1", 50000),
        headers={"Origin": origin},
    )

    response = client.post("/api/llm/codex/login/browser")

    assert response.status_code == 403
    assert runtime.browser_calls == 0


def test_configured_cors_origin_is_the_auth_origin_allowlist(
    runtime: FakeCodexRuntime,
) -> None:
    allowed_origin = "https://dashboard.example.test"
    app = create_app(
        codex_runtime=runtime,  # type: ignore[arg-type]
        cors_origins=(allowed_origin,),
    )
    client = TestClient(
        app,
        client=("127.0.0.1", 50000),
        headers={"Origin": allowed_origin},
    )

    account_response = client.get("/api/llm/codex/account")
    preflight_response = client.options(
        "/api/llm/codex/login/browser",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert account_response.status_code == 200
    assert preflight_response.status_code == 200
    assert preflight_response.headers["access-control-allow-origin"] == allowed_origin


def test_dashboard_cors_origins_support_launcher_selected_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:4317,http://127.0.0.1:4317,http://[::1]:4317",
    )

    assert resolve_dashboard_cors_origins() == (
        "http://localhost:4317",
        "http://127.0.0.1:4317",
        "http://[::1]:4317",
    )


def test_dashboard_cors_origins_reject_wildcards() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        resolve_dashboard_cors_origins(("*",))


@pytest.mark.parametrize(
    ("client_host", "headers"),
    [
        ("203.0.113.10", {"Origin": "http://localhost:3000"}),
        ("127.0.0.1", {"Origin": "https://example.com"}),
        ("127.0.0.1", {"Origin": "null"}),
        ("127.0.0.1", {"Origin": "http://localhost.example.com"}),
        ("127.0.0.1", {"Referer": "https://example.com/settings"}),
    ],
)
def test_auth_routes_reject_nonlocal_client_or_origin(
    runtime: FakeCodexRuntime,
    client_host: str,
    headers: dict[str, str],
) -> None:
    client = _build_client(runtime, client_host=client_host, headers=headers)

    response = client.post("/api/llm/codex/login/browser")

    assert response.status_code == 403
    assert runtime.browser_calls == 0


def test_auth_routes_allow_direct_loopback_clients_without_origin(
    runtime: FakeCodexRuntime,
) -> None:
    client = _build_client(runtime, headers={"Accept": "application/json"})

    response = client.get("/api/llm/codex/account")

    assert response.status_code == 200
    assert runtime.refresh_calls == 1


def test_browser_login_returns_pollable_attempt(runtime: FakeCodexRuntime) -> None:
    snapshot = runtime.browser_login
    runtime.browser_login = SimpleNamespace(
        login_id=snapshot.login_id,
        flow=snapshot.flow,
        status=snapshot.status,
        auth_url=snapshot.auth_url,
        verification_url=snapshot.verification_url,
        user_code=snapshot.user_code,
        error=snapshot.error,
        created_at=snapshot.created_at,
        completed_at=snapshot.completed_at,
        access_token="secret-login-token",
    )
    client = _build_client(runtime)

    response = client.post("/api/llm/codex/login/browser")

    assert response.status_code == 202
    assert response.json() == {
        "login_id": "login-123",
        "flow": "browser",
        "status": "pending",
        "auth_url": "https://chatgpt.com/auth",
        "verification_url": None,
        "user_code": None,
        "error": None,
        "created_at": "2026-07-31T12:00:00+00:00",
        "completed_at": None,
    }
    assert "secret-login-token" not in response.text


def test_device_code_login_returns_verification_details(runtime: FakeCodexRuntime) -> None:
    client = _build_client(runtime)

    response = client.post("/api/llm/codex/login/device-code")

    assert response.status_code == 202
    payload = response.json()
    assert payload["flow"] == "device_code"
    assert payload["verification_url"] == "https://auth.openai.com/codex/device"
    assert payload["user_code"] == "ABCD-1234"
    assert payload["auth_url"] is None


def test_login_attempt_can_be_polled_and_cancelled(runtime: FakeCodexRuntime) -> None:
    client = _build_client(runtime)

    pending = client.get("/api/llm/codex/login/login-123")
    cancelled = client.delete("/api/llm/codex/login/login-123")
    polled = client.get("/api/llm/codex/login/login-123")

    assert pending.status_code == 200
    assert pending.json()["status"] == "pending"
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "canceled"
    assert cancelled.json()["auth_url"] is None
    assert polled.json()["status"] == "canceled"
    assert runtime.cancel_calls == ["login-123"]


def test_active_login_can_be_recovered_without_browser_storage(
    runtime: FakeCodexRuntime,
) -> None:
    client = _build_client(runtime)

    empty = client.get("/api/llm/codex/login/active")
    started = client.post("/api/llm/codex/login/browser")
    recovered = client.get("/api/llm/codex/login/active")
    client.delete("/api/llm/codex/login/login-123")
    cleared = client.get("/api/llm/codex/login/active")

    assert empty.status_code == 200
    assert empty.json() is None
    assert started.status_code == 202
    assert recovered.status_code == 200
    assert recovered.json() == started.json()
    assert cleared.status_code == 200
    assert cleared.json() is None


def test_unknown_login_attempt_returns_sanitized_404(runtime: FakeCodexRuntime) -> None:
    client = _build_client(runtime)

    response = client.get("/api/llm/codex/login/missing")

    assert response.status_code == 404
    assert response.json() == {
        "code": "codex_login_not_found",
        "error": "Codex login attempt was not found.",
    }
    assert "private runtime detail" not in response.text


def test_logout_returns_unauthenticated_account(runtime: FakeCodexRuntime) -> None:
    client = _build_client(runtime)

    response = client.post("/api/llm/codex/logout")

    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    assert response.json()["account_type"] is None
    assert runtime.logout_calls == 1


def test_login_conflict_returns_sanitized_409(runtime: FakeCodexRuntime) -> None:
    runtime.browser_error = CodexLoginConflictError("secret conflict detail")
    client = _build_client(runtime)

    response = client.post("/api/llm/codex/login/browser")

    assert response.status_code == 409
    assert response.json()["code"] == "codex_login_in_progress"
    assert "secret conflict detail" not in response.text


def test_runtime_unavailable_returns_sanitized_503(runtime: FakeCodexRuntime) -> None:
    runtime.refresh_error = CodexRuntimeUnavailableError("secret process path")
    client = _build_client(runtime)

    response = client.get("/api/llm/codex/account")

    assert response.status_code == 503
    assert response.json() == {
        "code": "codex_runtime_unavailable",
        "error": "Codex runtime is unavailable.",
    }
    assert "secret process path" not in response.text
