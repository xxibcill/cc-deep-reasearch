"""Focused coverage for Codex-backed Quick Script routing."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.config import Config
from cc_deep_research.content_gen import router as content_gen_router
from cc_deep_research.content_gen import (
    scripting_api_service as scripting_api_service_module,
)
from cc_deep_research.content_gen.agents import quality_evaluator as quality_evaluator_module
from cc_deep_research.content_gen.agents import scripting as scripting_agent_module
from cc_deep_research.content_gen.agents.quality_evaluator import (
    AGENT_ID as EVALUATOR_AGENT_ID,
)
from cc_deep_research.content_gen.agents.quality_evaluator import QualityEvaluatorAgent
from cc_deep_research.content_gen.agents.scripting import AGENT_ID, ScriptingAgent
from cc_deep_research.content_gen.models import QCResult, QualityEvaluation, ScriptingContext
from cc_deep_research.content_gen.scripting_api_service import ScriptingApiService
from cc_deep_research.content_gen.scripting_run_service import ScriptingRunService
from cc_deep_research.llm.base import LLMTransportType
from cc_deep_research.web_server import create_app


def test_quick_script_request_accepts_codex_route() -> None:
    request = content_gen_router.RunScriptingRequest(
        idea="Explain model routing",
        llm_route="codex",
    )

    assert request.llm_route == "codex"


def test_quality_evaluator_accepts_codex_route_override() -> None:
    evaluator = QualityEvaluatorAgent(
        Config(),
        llm_route="codex",
        codex_runtime=MagicMock(),
    )

    route = evaluator._router._registry.get_route(EVALUATOR_AGENT_ID)

    assert route.transport == LLMTransportType.CODEX_APP_SERVER


def test_scripting_components_share_injected_codex_runtime() -> None:
    config = Config()
    codex_runtime = MagicMock()

    agent = ScriptingAgent(
        config,
        llm_route="codex",
        codex_runtime=codex_runtime,
    )
    evaluator = QualityEvaluatorAgent(
        config,
        codex_runtime=codex_runtime,
    )
    api_service = ScriptingApiService(
        config=config,
        scripting_store=MagicMock(),
        codex_runtime=codex_runtime,
    )
    run_service = api_service._default_scripting_run_factory()

    assert agent._router._codex_runtime is codex_runtime
    assert agent._router._registry.get_route(AGENT_ID).transport == LLMTransportType.CODEX_APP_SERVER
    assert evaluator._router._codex_runtime is codex_runtime
    assert run_service._codex_runtime is codex_runtime


@pytest.mark.asyncio
async def test_iterative_scripting_routes_producer_and_evaluator_through_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, list[tuple[str | None, object | None]]] = {
        "producer": [],
        "evaluator": [],
    }
    codex_runtime = MagicMock()

    class FakeScriptingAgent:
        def __init__(
            self,
            _config: Config,
            *,
            llm_route: str | None = None,
            codex_runtime: object | None = None,
        ) -> None:
            captured["producer"].append((llm_route, codex_runtime))

        async def run_pipeline(
            self,
            raw_idea: str,
            *,
            progress_callback=None,
            iteration: int = 1,
        ) -> ScriptingContext:
            del progress_callback, iteration
            return ScriptingContext(raw_idea=raw_idea)

    class FakeQualityEvaluatorAgent:
        def __init__(
            self,
            _config: Config,
            *,
            llm_route: str | None = None,
            codex_runtime: object | None = None,
        ) -> None:
            captured["evaluator"].append((llm_route, codex_runtime))

        async def evaluate_scripting(self, **_kwargs: object) -> QualityEvaluation:
            return QualityEvaluation(
                iteration_number=1,
                overall_quality_score=1.0,
                passes_threshold=True,
            )

    monkeypatch.setattr(scripting_agent_module, "ScriptingAgent", FakeScriptingAgent)
    monkeypatch.setattr(
        quality_evaluator_module,
        "QualityEvaluatorAgent",
        FakeQualityEvaluatorAgent,
    )

    service = ScriptingRunService(Config(), codex_runtime=codex_runtime)
    result, iteration_state = await service.run_scripting_iterative(
        "Explain model routing",
        llm_route="codex",
    )

    assert result.raw_idea == "Explain model routing"
    assert iteration_state.is_converged is True
    assert captured == {
        "producer": [("codex", codex_runtime)],
        "evaluator": [("codex", codex_runtime)],
    }


@pytest.mark.asyncio
async def test_scripting_run_service_passes_codex_route_and_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    codex_runtime = MagicMock()

    class FakeScriptingAgent:
        def __init__(
            self,
            _config: Config,
            *,
            llm_route: str | None = None,
            codex_runtime: object | None = None,
        ) -> None:
            captured["llm_route"] = llm_route
            captured["codex_runtime"] = codex_runtime

        async def run_pipeline(
            self,
            raw_idea: str,
            *,
            progress_callback=None,
        ) -> ScriptingContext:
            del progress_callback
            return ScriptingContext(raw_idea=raw_idea)

    monkeypatch.setattr(
        scripting_agent_module,
        "ScriptingAgent",
        FakeScriptingAgent,
    )
    service = ScriptingRunService(
        Config(),
        codex_runtime=codex_runtime,
    )

    result = await service.run_scripting(
        "Explain model routing",
        llm_route="codex",
    )

    assert result.raw_idea == "Explain model routing"
    assert captured == {
        "llm_route": "codex",
        "codex_runtime": codex_runtime,
    }


def test_quick_script_uses_codex_config_saved_after_app_start(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    captured: dict[str, object] = {}

    class FakeScriptingRunService:
        def __init__(
            self,
            config: Config,
            *,
            codex_runtime: object | None = None,
        ) -> None:
            captured["enabled"] = config.llm.codex.enabled
            captured["model"] = config.llm.codex.model
            captured["reasoning_effort"] = config.llm.codex.reasoning_effort
            captured["codex_runtime"] = codex_runtime

        async def run_scripting(
            self,
            idea: str,
            *,
            llm_route: str | None = None,
        ) -> ScriptingContext:
            captured["llm_route"] = llm_route
            return ScriptingContext(
                raw_idea=idea,
                qc=QCResult(final_script="Codex config refreshed"),
            )

    monkeypatch.setattr(
        scripting_api_service_module,
        "ScriptingRunService",
        FakeScriptingRunService,
    )
    app = create_app()
    client = TestClient(app)

    patch_response = client.patch(
        "/api/config",
        json={
            "updates": {
                "llm.codex.enabled": True,
                "llm.codex.model": "gpt-5.6-sol",
                "llm.codex.reasoning_effort": "high",
            }
        },
    )
    run_response = client.post(
        "/api/content-gen/scripting",
        json={
            "idea": "Explain model routing",
            "iterative_mode": False,
            "llm_route": "codex",
        },
    )

    assert patch_response.status_code == 200
    assert run_response.status_code == 200
    assert captured["enabled"] is True
    assert captured["model"] == "gpt-5.6-sol"
    assert captured["reasoning_effort"] == "high"
    assert captured["llm_route"] == "codex"
    assert captured["codex_runtime"] is app.state.dashboard_runtime.codex_runtime


def test_quick_script_endpoint_forwards_codex_without_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_run_scripting(
        _self: ScriptingApiService,
        idea: str,
        iterative_mode: bool | None = None,
        max_iterations: int | None = None,
        llm_route: str | None = None,
    ) -> object:
        captured.update(
            {
                "idea": idea,
                "iterative_mode": iterative_mode,
                "max_iterations": max_iterations,
                "llm_route": llm_route,
            }
        )
        return object()

    monkeypatch.setattr(
        ScriptingApiService,
        "run_scripting",
        fake_run_scripting,
    )
    monkeypatch.setattr(
        ScriptingApiService,
        "serialize_result",
        staticmethod(lambda _result: {"accepted": True}),
    )

    response = TestClient(create_app()).post(
        "/api/content-gen/scripting",
        json={
            "idea": "Explain model routing",
            "iterative_mode": False,
            "llm_route": "codex",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True}
    assert captured == {
        "idea": "Explain model routing",
        "iterative_mode": False,
        "max_iterations": None,
        "llm_route": "codex",
    }
