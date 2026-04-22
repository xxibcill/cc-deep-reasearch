"""Service-level tests for backlog-chat domain behavior.

These tests cover:
- build_apply_operations validation logic
- apply_operations end-to-end behavior with BacklogService
- BacklogChatAgent.respond conversation mode

Route-level tests (HTTP contracts) live in test_content_gen_backlog_chat.py.
"""

from __future__ import annotations

import json

import pytest

from cc_deep_research.content_gen.agents.backlog_chat import (
    BacklogChatAgent,
    BacklogChatOperation,
    apply_operations,
    build_apply_operations,
)
from cc_deep_research.content_gen.backlog_service import BacklogService
from cc_deep_research.content_gen.models import BacklogItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def backlog_service(tmp_path) -> BacklogService:
    """Return a BacklogService backed by a temporary store."""
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(path=tmp_path / "backlog.yaml")
    return BacklogService(config=None, store=store)


@pytest.fixture
def sample_backlog_items() -> list[BacklogItem]:
    """Return a list of sample BacklogItems for testing."""
    return [
        BacklogItem(
            idea_id="item-001",
            idea="AI coding assistants",
            category="trend-responsive",
            audience="",
            problem="",
            source="",
            why_now="",
            potential_hook="",
            content_type="",
            evidence="",
            risk_level="medium",
            priority_score=7.0,
            status="backlog",
        ),
        BacklogItem(
            idea_id="item-002",
            idea="Remote work tools",
            category="authority-building",
            audience="",
            problem="",
            source="",
            why_now="",
            potential_hook="",
            content_type="",
            evidence="",
            risk_level="low",
            priority_score=5.0,
            status="backlog",
        ),
    ]


# ---------------------------------------------------------------------------
# build_apply_operations tests
# ---------------------------------------------------------------------------


def test_build_apply_operations_rejects_unknown_kind(sample_backlog_items) -> None:
    """Unknown operation kinds should be reported as errors."""
    operations = [
        {"kind": "delete_item", "idea_id": "item-001", "reason": "Test", "fields": {}},
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    assert validated == []
    assert len(errors) == 1
    assert "unknown operation kind" in errors[0]


def test_build_apply_operations_rejects_update_without_idea_id(sample_backlog_items) -> None:
    """update_item without idea_id should be reported as an error."""
    operations = [
        {"kind": "update_item", "reason": "No idea_id", "fields": {"idea": "New idea"}},
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    assert validated == []
    assert len(errors) == 1
    assert "idea_id" in errors[0]


def test_build_apply_operations_rejects_update_nonexistent_id(sample_backlog_items) -> None:
    """update_item with non-existent idea_id should be reported as an error."""
    operations = [
        {
            "kind": "update_item",
            "idea_id": "nonexistent-id",
            "reason": "Item does not exist",
            "fields": {"idea": "New idea"},
        },
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    assert validated == []
    assert len(errors) == 1
    assert "item not found" in errors[0]


def test_build_apply_operations_rejects_update_with_no_supported_fields(
    sample_backlog_items,
) -> None:
    """update_item with no supported fields should be reported as an error."""
    operations = [
        {
            "kind": "update_item",
            "idea_id": "item-001",
            "reason": "Only unsupported fields",
            "fields": {"unsupported_field": "value", "another_unsupported": "x"},
        },
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    assert validated == []
    assert len(errors) == 1
    assert "no supported fields" in errors[0]


def test_build_apply_operations_rejects_create_without_title_or_idea(
    sample_backlog_items,
) -> None:
    """create_item without title or idea should be reported as an error."""
    operations = [
        {
            "kind": "create_item",
            "reason": "No title or idea",
            "fields": {"category": "trend-responsive"},
        },
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    assert validated == []
    assert len(errors) == 1
    assert "requires fields.title, fields.idea, or fields.raw_idea" in errors[0]


def test_build_apply_operations_accepts_valid_update_item(sample_backlog_items) -> None:
    """Valid update_item should be validated successfully."""
    operations = [
        {
            "kind": "update_item",
            "idea_id": "item-001",
            "reason": "Narrow the scope",
            "fields": {"idea": "Updated AI coding assistants"},
        },
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    assert len(validated) == 1
    assert validated[0].kind == "update_item"
    assert validated[0].idea_id == "item-001"
    assert validated[0].fields["idea"] == "Updated AI coding assistants"
    assert errors == []


def test_build_apply_operations_accepts_valid_create_item(sample_backlog_items) -> None:
    """Valid create_item should be validated successfully."""
    operations = [
        {
            "kind": "create_item",
            "reason": "New idea",
            "fields": {"idea": "New backlog idea", "category": "authority-building"},
        },
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    assert len(validated) == 1
    assert validated[0].kind == "create_item"
    assert validated[0].idea_id is None
    assert validated[0].fields["idea"] == "New backlog idea"
    assert errors == []


def test_build_apply_operations_partial_validation_returns_mixed_results(
    sample_backlog_items,
) -> None:
    """When some operations are valid and others invalid, both validated and errors are returned."""
    operations = [
        {
            "kind": "update_item",
            "idea_id": "item-001",
            "reason": "Valid update",
            "fields": {"idea": "Updated idea"},
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
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    assert len(validated) == 2
    assert len(errors) == 1
    assert "item not found" in errors[0]


def test_build_apply_operations_rejects_unsupported_update_fields(sample_backlog_items) -> None:
    """update_item with unsupported fields should only keep supported ones (status, priority_score)."""
    operations = [
        {
            "kind": "update_item",
            "idea_id": "item-001",
            "reason": "Mix of supported and unsupported",
            "fields": {"priority_score": "oops", "status": "bogus"},
        },
    ]
    validated, errors = build_apply_operations(operations, sample_backlog_items)
    # The validation passes but the fields are sanitized - status is supported, priority_score is not
    # build_apply_operations passes through sanitized fields; the 400 from apply route is from validation
    assert len(validated) == 1
    # status is in SUPPORTED_UPDATE_FIELDS but "bogus" may fail type validation at apply time
    assert validated[0].fields.get("status") is not None


# ---------------------------------------------------------------------------
# apply_operations tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_operations_creates_new_item(
    backlog_service: BacklogService,
    sample_backlog_items: list[BacklogItem],
) -> None:
    """apply_operations should create a new backlog item."""
    # Pre-load some items so backlog exists
    for item in sample_backlog_items:
        backlog_service.create_item(
            idea=item.idea,
            category=item.category,
            risk_level=item.risk_level,
        )

    operations = [
        BacklogChatOperation(
            kind="create_item",
            idea_id=None,
            reason="This fills a missing lane.",
            fields={
                "idea": "New idea from chat",
                "category": "authority-building",
                "audience": "Beginner founders",
                "problem": "They copy advanced tactics too early.",
            },
        ),
    ]

    applied, items, errors = await apply_operations(operations, backlog_service)

    assert applied == 1
    assert len(items) == 1
    assert items[0].idea == "New idea from chat"
    assert items[0].category == "authority-building"
    assert errors == []


@pytest.mark.asyncio
async def test_apply_operations_updates_existing_item(
    backlog_service: BacklogService,
    sample_backlog_items: list[BacklogItem],
) -> None:
    """apply_operations should update an existing backlog item."""
    # Pre-load items
    item_ids = []
    for item in sample_backlog_items:
        created = backlog_service.create_item(
            idea=item.idea,
            category=item.category,
            risk_level=item.risk_level,
        )
        item_ids.append(created.idea_id)

    operations = [
        BacklogChatOperation(
            kind="update_item",
            idea_id=item_ids[0],
            reason="Narrow the scope",
            fields={"idea": "Updated idea via chat"},
        ),
    ]

    applied, items, errors = await apply_operations(operations, backlog_service)

    assert applied == 1
    assert len(items) == 1
    assert items[0].idea == "Updated idea via chat"
    assert errors == []


@pytest.mark.asyncio
async def test_apply_operations_handles_partial_failure(
    backlog_service: BacklogService,
    sample_backlog_items: list[BacklogItem],
) -> None:
    """apply_operations should apply valid operations and report errors for invalid ones."""
    # Pre-load items
    item_ids = []
    for item in sample_backlog_items:
        created = backlog_service.create_item(
            idea=item.idea,
            category=item.category,
            risk_level=item.risk_level,
        )
        item_ids.append(created.idea_id)

    operations = [
        BacklogChatOperation(
            kind="update_item",
            idea_id=item_ids[0],
            reason="Valid update",
            fields={"idea": "Updated first idea"},
        ),
        BacklogChatOperation(
            kind="update_item",
            idea_id="nonexistent-id",
            reason="Invalid — item does not exist",
            fields={"idea": "Should fail"},
        ),
        BacklogChatOperation(
            kind="create_item",
            idea_id=None,
            reason="Valid create",
            fields={"idea": "New third idea"},
        ),
    ]

    applied, items, errors = await apply_operations(operations, backlog_service)

    # At least the valid operations should have been applied
    assert applied >= 1
    # The error for the failed update should be reported
    assert len(errors) >= 1
    assert any("nonexistent-id" in err for err in errors)


@pytest.mark.asyncio
async def test_apply_operations_rejects_invalid_status_field(
    backlog_service: BacklogService,
    sample_backlog_items: list[BacklogItem],
) -> None:
    """apply_operations should report an error for invalid status values."""
    # Pre-load an item
    item_ids = []
    for item in sample_backlog_items:
        created = backlog_service.create_item(
            idea=item.idea,
            category=item.category,
            risk_level=item.risk_level,
        )
        item_ids.append(created.idea_id)

    operations = [
        BacklogChatOperation(
            kind="update_item",
            idea_id=item_ids[0],
            reason="Inject unsupported and invalid fields",
            fields={"priority_score": "oops", "status": "bogus"},
        ),
    ]

    applied, items, errors = await apply_operations(operations, backlog_service)

    # The invalid status should cause an error
    assert applied == 0
    assert len(errors) == 1
    assert "status" in errors[0]


@pytest.mark.asyncio
async def test_apply_operations_persists_all_supported_create_fields(
    backlog_service: BacklogService,
    sample_backlog_items: list[BacklogItem],
) -> None:
    """apply_operations should persist the full supported create-item field set."""
    # Pre-load items so backlog exists
    for item in sample_backlog_items:
        backlog_service.create_item(
            idea=item.idea,
            category=item.category,
            risk_level=item.risk_level,
        )

    operations = [
        BacklogChatOperation(
            kind="create_item",
            idea_id=None,
            reason="Create a fully-populated item",
            fields={
                "idea": "New idea from chat",
                "category": "authority-building",
                "audience": "Beginner founders",
                "problem": "They copy advanced tactics too early.",
                "source": "operator interview",
                "why_now": "This week showed the same pattern again.",
                "hook": "You are copying tactics two stages too early.",
                "content_type": "short video",
                "evidence": "Three customer calls",
                "risk_level": "high",
            },
        ),
    ]

    applied, items, errors = await apply_operations(operations, backlog_service)

    assert applied == 1
    assert errors == []

    item = items[0]
    assert item.source == "operator interview"
    assert item.why_now == "This week showed the same pattern again."
    assert item.hook == "You are copying tactics two stages too early."
    assert item.content_type == "short video"
    assert item.evidence == "Three customer calls"
    assert item.risk_level == "high"


# ---------------------------------------------------------------------------
# BacklogChatAgent respond tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backlog_chat_agent_drops_operations_in_conversation_mode(
    monkeypatch,
    tmp_path,
) -> None:
    """BacklogChatAgent.respond in conversation mode should never surface proposed mutations."""
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
