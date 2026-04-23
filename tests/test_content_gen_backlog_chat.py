"""Route-level tests for backlog-chat HTTP endpoints.

These tests cover HTTP-level concerns:
- Status codes
- Request validation (Pydantic 422 errors)
- Response envelope structure

Domain behavior (apply_operations, build_apply_operations, agent respond)
is tested in test_backlog_chat_service.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.web_server import create_app

# ---------------------------------------------------------------------------
# Respond route
# ---------------------------------------------------------------------------


def test_backlog_chat_respond_returns_proposal_from_mocked_llm(
    monkeypatch,
    tmp_path,
):
    """respond route should return a parsed proposal from mocked LLM output."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    from cc_deep_research.content_gen.agents.backlog_chat import BacklogChatAgent

    async def fake_respond(
        self,
        messages,
        backlog_items,
        *,
        strategy=None,
        selected_idea_id=None,
        mode="edit",
    ):
        from cc_deep_research.content_gen.agents.backlog_chat import BacklogChatResponse

        return BacklogChatResponse(
            reply_markdown="Here's what I would tighten first.",
            apply_ready=True,
            warnings=[],
            operations=[
                {
                    "kind": "update_item",
                    "idea_id": "item-001",
                    "reason": "Too broad for an authority-building slot.",
                    "fields": {"idea": "Narrower replacement idea"},
                }
            ],
            mentioned_idea_ids=["item-001"],
        )

    monkeypatch.setattr(BacklogChatAgent, "respond", fake_respond)

    client = TestClient(create_app())

    response = client.post(
        "/api/content-gen/backlog-chat/respond",
        json={
            "messages": [{"role": "user", "content": "Help me tighten this backlog."}],
            "backlog_items": [
                {
                    "idea_id": "item-001",
                    "idea": "AI coding assistants",
                    "category": "trend-responsive",
                    "audience": "",
                    "problem": "",
                    "source": "",
                    "why_now": "",
                    "potential_hook": "",
                    "content_type": "",
                    "evidence": "",
                    "risk_level": "medium",
                    "priority_score": 7.0,
                    "status": "backlog",
                }
            ],
            "strategy": None,
            "selected_idea_id": None,
        },
    )

    assert response.status_code == 200
    data = response.json()
    # HTTP-level assertions: status code and response envelope
    assert data["apply_ready"] is True
    assert len(data["operations"]) == 1
    assert data["operations"][0]["kind"] == "update_item"
    assert "item-001" in data["mentioned_idea_ids"]


def test_backlog_chat_respond_falls_back_safely_on_malformed_model_output(
    monkeypatch,
    tmp_path,
):
    """respond route should return safe fallback on malformed LLM output."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    from cc_deep_research.content_gen.agents.backlog_chat import BacklogChatAgent

    async def fake_respond_malformed(
        self,
        messages,
        backlog_items,
        *,
        strategy=None,
        selected_idea_id=None,
        mode="edit",
    ):
        from cc_deep_research.content_gen.agents.backlog_chat import BacklogChatResponse

        return BacklogChatResponse(
            reply_markdown="I had trouble generating a proposal just now. Feel free to try again.",
            apply_ready=False,
            warnings=["LLM call failed: Something went wrong"],
            operations=[],
            mentioned_idea_ids=[],
        )

    monkeypatch.setattr(BacklogChatAgent, "respond", fake_respond_malformed)

    client = TestClient(create_app())

    response = client.post(
        "/api/content-gen/backlog-chat/respond",
        json={
            "messages": [{"role": "user", "content": "bad output"}],
            "backlog_items": [],
            "strategy": None,
            "selected_idea_id": None,
        },
    )

    assert response.status_code == 200
    data = response.json()
    # HTTP-level assertions: status code and safe fallback envelope
    assert data["apply_ready"] is False
    assert data["operations"] == []
    assert len(data["warnings"]) > 0


# ---------------------------------------------------------------------------
# Apply route
# ---------------------------------------------------------------------------


def test_backlog_chat_apply_rejects_unknown_operation_kind(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should return 422 for unknown operation kinds via Pydantic validation."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create an item
    create_resp = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Some idea"},
    )
    assert create_resp.status_code == 201

    # Sending "delete_item" should fail at the Pydantic model level (422)
    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={
            "operations": [
                {
                    "kind": "delete_item",
                    "idea_id": create_resp.json()["idea_id"],
                    "reason": "Should be rejected",
                    "fields": {},
                },
            ],
        },
    )

    # Pydantic rejects unknown literal with 422
    assert response.status_code == 422


def test_backlog_chat_apply_returns_200_for_empty_operations(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should return 200 with empty applied list for empty operations."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={"operations": []},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["applied"] == 0
    assert data["items"] == []
    assert data["errors"] == []
