"""Tests for the backlog chat feature (content-gen)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.web_server import create_app


class _FakeBacklogChatAgent:
    """Fake agent that returns a pre-configured response."""

    def __init__(self, response: dict) -> None:
        self._response = response
        self.call_count = 0

    async def respond(
        self,
        messages,
        backlog_items,
        *,
        strategy=None,
        selected_idea_id=None,
        mode="edit",
    ):
        self.call_count += 1
        return self._response


class _FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content


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
    assert data["apply_ready"] is True
    assert len(data["operations"]) == 1
    assert data["operations"][0]["kind"] == "update_item"
    assert data["operations"][0]["idea_id"] == "item-001"
    assert data["operations"][0]["fields"]["idea"] == "Narrower replacement idea"
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
        # Simulate the agent returning a safe fallback response
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
    # Should return safe fallback structure
    assert data["apply_ready"] is False
    assert data["operations"] == []
    assert len(data["warnings"]) > 0


def test_backlog_chat_respond_passes_conversation_mode(
    monkeypatch,
    tmp_path,
):
    """respond route should pass conversation mode through to the agent."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    from cc_deep_research.content_gen.agents.backlog_chat import BacklogChatAgent

    observed: dict[str, str] = {}

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

        observed["mode"] = mode
        return BacklogChatResponse(
            reply_markdown="Tell me more about the audience and outcome you want.",
            apply_ready=False,
            warnings=[],
            operations=[],
            mentioned_idea_ids=[],
        )

    monkeypatch.setattr(BacklogChatAgent, "respond", fake_respond)

    client = TestClient(create_app())

    response = client.post(
        "/api/content-gen/backlog-chat/respond",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "backlog_items": [],
            "strategy": None,
            "selected_idea_id": None,
            "mode": "conversation",
        },
    )

    assert response.status_code == 200
    assert observed["mode"] == "conversation"
    assert response.json()["operations"] == []


@pytest.mark.asyncio
async def test_backlog_chat_agent_drops_operations_in_conversation_mode(
    monkeypatch,
    tmp_path,
):
    """conversation mode should never surface proposed mutations."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    from cc_deep_research.content_gen.agents.backlog_chat import BacklogChatAgent
    from cc_deep_research.content_gen.models import BacklogItem

    async def fake_call_llm(self, system_prompt, user_prompt, *, temperature=0.5):
        return json.dumps(
            {
                "reply_markdown": "We should narrow the audience before we edit the backlog.",
                "apply_ready": True,
                "warnings": [],
                "operations": [
                    {
                        "kind": "update_item",
                        "idea_id": "item-001",
                        "reason": "Too broad",
                        "fields": {"audience": "Early-stage founders"},
                    }
                ],
                "mentioned_idea_ids": ["item-001"],
            }
        )

    monkeypatch.setattr(BacklogChatAgent, "_call_llm", fake_call_llm)

    agent = BacklogChatAgent()
    response = await agent.respond(
        messages=[{"role": "user", "content": "hi"}],
        backlog_items=[BacklogItem(idea_id="item-001", idea="AI coding assistants")],
        mode="conversation",
    )

    assert response.apply_ready is False
    assert response.operations == []


# ---------------------------------------------------------------------------
# Apply route
# ---------------------------------------------------------------------------

def test_backlog_chat_apply_creates_new_item(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should create a new backlog item."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create an item first so the backlog exists
    existing = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Existing idea"},
    )
    assert existing.status_code == 201

    # Apply a create_item operation
    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={
            "operations": [
                {
                    "kind": "create_item",
                    "reason": "This fills a missing lane.",
                    "fields": {
                        "idea": "New idea from chat",
                        "category": "authority-building",
                        "audience": "Beginner founders",
                        "problem": "They copy advanced tactics too early.",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["applied"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["idea"] == "New idea from chat"
    assert data["items"][0]["category"] == "authority-building"
    assert data["errors"] == []

    # Verify item is in the backlog
    list_resp = client.get("/api/content-gen/backlog")
    items = list_resp.json()["items"]
    ideas = {item["idea"] for item in items}
    assert "New idea from chat" in ideas


def test_backlog_chat_apply_updates_existing_item(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should update an existing backlog item."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create an item
    create_resp = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Original idea", "category": "trend-responsive"},
    )
    idea_id = create_resp.json()["idea_id"]

    # Apply an update_item operation
    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={
            "operations": [
                {
                    "kind": "update_item",
                    "idea_id": idea_id,
                    "reason": "Narrow the scope",
                    "fields": {"idea": "Updated idea via chat"},
                },
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["applied"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["idea"] == "Updated idea via chat"
    assert data["errors"] == []


def test_backlog_chat_apply_rejects_unknown_operation_kind(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should reject unknown operation kinds via Pydantic validation."""
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


def test_backlog_chat_apply_rejects_update_without_idea_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should reject update_item without idea_id."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={
            "operations": [
                {
                    "kind": "update_item",
                    "reason": "No idea_id provided",
                    "fields": {"idea": "New idea"},
                },
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["applied"] == 0
    assert len(data["errors"]) > 0
    assert "idea_id" in data["errors"][0]


def test_backlog_chat_apply_rejects_create_without_idea_in_fields(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should reject create_item without idea in fields."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={
            "operations": [
                {
                    "kind": "create_item",
                    "reason": "No idea field",
                    "fields": {"category": "trend-responsive"},
                },
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["applied"] == 0
    assert len(data["errors"]) > 0
    assert "fields.idea" in data["errors"][0]


def test_backlog_chat_apply_returns_structured_errors_on_partial_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should return structured errors and not crash on invalid operations."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create two items
    resp1 = client.post("/api/content-gen/backlog", json={"idea": "First idea"})
    resp2 = client.post("/api/content-gen/backlog", json={"idea": "Second idea"})
    id1 = resp1.json()["idea_id"]
    id2 = resp2.json()["idea_id"]

    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={
            "operations": [
                {
                    "kind": "update_item",
                    "idea_id": id1,
                    "reason": "Valid update",
                    "fields": {"idea": "Updated first idea"},
                },
                {
                    "kind": "update_item",
                    "idea_id": "nonexistent-id",
                    "reason": "Invalid — item does not exist",
                    "fields": {"idea": "Should fail"},
                },
                {
                    "kind": "create_item",
                    "reason": "Valid create",
                    "fields": {"idea": "New third idea"},
                },
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    # At least the valid operations should have been applied
    assert data["applied"] >= 1
    # The error for the failed update should be reported
    assert len(data["errors"]) >= 1
    assert any("nonexistent-id" in err for err in data["errors"])


def test_backlog_chat_apply_rejects_unsupported_or_invalid_update_fields(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should reject invalid update values and unsupported fields."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    create_resp = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Original idea", "category": "trend-responsive"},
    )
    idea_id = create_resp.json()["idea_id"]

    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={
            "operations": [
                {
                    "kind": "update_item",
                    "idea_id": idea_id,
                    "reason": "Inject unsupported and invalid fields",
                    "fields": {"priority_score": "oops", "status": "bogus"},
                },
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["applied"] == 0
    assert len(data["errors"]) == 1
    assert "status" in data["errors"][0]

    list_resp = client.get("/api/content-gen/backlog")
    item = next(item for item in list_resp.json()["items"] if item["idea_id"] == idea_id)
    assert item["status"] == "backlog"
    assert item["priority_score"] == 0.0


def test_backlog_chat_apply_persists_all_supported_create_fields(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply route should persist the full supported create-item field set."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    response = client.post(
        "/api/content-gen/backlog-chat/apply",
        json={
            "operations": [
                {
                    "kind": "create_item",
                    "reason": "Create a fully-populated item",
                    "fields": {
                        "idea": "New idea from chat",
                        "category": "authority-building",
                        "audience": "Beginner founders",
                        "problem": "They copy advanced tactics too early.",
                        "source": "operator interview",
                        "why_now": "This week showed the same pattern again.",
                        "potential_hook": "You are copying tactics two stages too early.",
                        "content_type": "short video",
                        "evidence": "Three customer calls",
                        "risk_level": "high",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["applied"] == 1
    assert data["errors"] == []

    item = data["items"][0]
    assert item["source"] == "operator interview"
    assert item["why_now"] == "This week showed the same pattern again."
    assert item["potential_hook"] == "You are copying tactics two stages too early."
    assert item["content_type"] == "short video"
    assert item["evidence"] == "Three customer calls"
    assert item["risk_level"] == "high"
