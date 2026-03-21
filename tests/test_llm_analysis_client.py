"""Tests for routed analysis client integration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cc_deep_research.agents.ai_analysis_service import AIAnalysisService
from cc_deep_research.agents.llm_analysis_client import LLMAnalysisClient


def _request_executor(operation: str, prompt: str) -> str:
    if not operation or not prompt:
        raise AssertionError("operation and prompt are required")
    return '{"themes":[{"name":"Theme","description":"Desc","key_points":["Point"],"supporting_sources":["https://example.com"]}]}'


class TestLLMAnalysisClient:
    """Tests for the routed LLM analysis client."""

    def test_init_requires_request_executor(self) -> None:
        """The client should fail fast without an execution backend."""
        with pytest.raises(ValueError, match="request_executor"):
            LLMAnalysisClient({})

    def test_extract_themes_uses_request_executor(self) -> None:
        """Theme extraction should execute through the injected request executor."""
        operations: list[str] = []

        def executor(operation: str, prompt: str) -> str:
            operations.append(operation)
            assert "identify 3 major themes" in prompt
            return _request_executor(operation, prompt)

        client = LLMAnalysisClient({"request_executor": executor})

        themes = client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Title", "content": "Content"}],
            query="test query",
            num_themes=3,
        )

        assert operations == ["extract_themes"]
        assert themes[0]["name"] == "Theme"

    def test_parse_cross_reference_response_returns_json_payload(self) -> None:
        """Cross-reference parsing should preserve structured JSON responses."""
        client = LLMAnalysisClient({"request_executor": _request_executor})

        result = client._parse_cross_reference_response(
            '{"consensus_points":[{"claim":"A"}],"disagreement_points":[{"claim":"B"}]}'
        )

        assert result["consensus_points"] == [{"claim": "A"}]
        assert result["disagreement_points"] == [{"claim": "B"}]

    def test_parse_synthesis_response_adds_missing_fields(self) -> None:
        """Synthesis parsing should backfill summary and detail point defaults."""
        client = LLMAnalysisClient({"request_executor": _request_executor})

        findings = client._parse_synthesis_response(
            '{"findings":[{"title":"Finding","description":"Longer description","evidence":["https://example.com"]}]}'
        )

        assert findings[0]["summary"] == "Longer description"
        assert findings[0]["detail_points"] == []


class TestAIAnalysisService:
    """Tests for routed AI analysis service initialization."""

    def test_api_mode_requires_router(self) -> None:
        """Strict API mode should require a configured router."""
        with pytest.raises(ValueError, match="requires an LLM router"):
            AIAnalysisService({"ai_integration_method": "api"})

    def test_hybrid_mode_without_router_uses_heuristic_fallback(self) -> None:
        """Hybrid mode should tolerate missing routed LLM support."""
        service = AIAnalysisService({"ai_integration_method": "hybrid"})

        assert service._llm_client is None

    def test_router_backed_client_initializes_when_route_is_available(self) -> None:
        """Available routed LLM support should initialize the analysis client."""
        router = MagicMock()
        router.is_available.return_value = True
        router.execute = MagicMock()

        service = AIAnalysisService(
            {"ai_integration_method": "api"},
            llm_router=router,
        )

        assert service._llm_client is not None

    def test_routed_theme_extraction_marks_usage(self) -> None:
        """Successful routed analysis should mark routed LLM usage."""
        router = MagicMock()
        router.is_available.return_value = True
        service = AIAnalysisService(
            {"ai_integration_method": "hybrid"},
            llm_router=router,
        )
        service._llm_client = MagicMock()
        service._llm_client.extract_themes.return_value = [
            {
                "name": "Theme",
                "description": "Desc",
                "key_points": ["Point"],
                "supporting_sources": ["https://example.com"],
            }
        ]

        themes = service.extract_themes_semantically(
            sources=[
                MagicMock(
                    url="https://example.com",
                    title="Title",
                    content="Long enough content " * 20,
                    snippet="",
                )
            ],
            query="test query",
            num_themes=3,
        )

        assert len(themes) == 1
        assert service.routed_llm_used is True

    def test_routed_theme_extraction_failure_emits_degradation(self) -> None:
        """Hybrid fallback should emit a degradation event when routed analysis fails."""
        router = MagicMock()
        router.is_available.return_value = True
        monitor = MagicMock()
        service = AIAnalysisService(
            {"ai_integration_method": "hybrid"},
            llm_router=router,
            monitor=monitor,
        )
        service._llm_client = MagicMock()
        service._llm_client.extract_themes.side_effect = RuntimeError("boom")
        service._ai_executor.extract_themes = MagicMock(return_value=[
            {
                "name": "Fallback Theme",
                "description": "Desc",
                "key_points": ["Point"],
                "supporting_sources": ["https://example.com"],
            }
        ])

        themes = service.extract_themes_semantically(
            sources=[
                MagicMock(
                    url="https://example.com",
                    title="Title",
                    content="Long enough content " * 20,
                    snippet="",
                )
            ],
            query="test query",
            num_themes=3,
        )

        assert len(themes) == 1
        assert service.routed_llm_used is False
        monitor.emit_degradation_detected.assert_called_once()
