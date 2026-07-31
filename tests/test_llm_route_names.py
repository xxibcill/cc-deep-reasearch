"""Tests for the shared public route-name mapping."""

from cc_deep_research.llm.base import LLMTransportType, transport_from_route_name


def test_transport_from_route_name_maps_all_public_routes() -> None:
    assert transport_from_route_name("openrouter") == LLMTransportType.OPENROUTER_API
    assert transport_from_route_name("cerebras") == LLMTransportType.CEREBRAS_API
    assert transport_from_route_name("anthropic") == LLMTransportType.ANTHROPIC_API
    assert transport_from_route_name("codex") == LLMTransportType.CODEX_APP_SERVER
    assert transport_from_route_name("heuristic") == LLMTransportType.HEURISTIC
    assert transport_from_route_name("unknown") is None
