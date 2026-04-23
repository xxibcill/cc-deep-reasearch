"""Contract tests for storage migration and legacy field normalization.

These tests cover:
- YAML-to-SQLite migration for backlog and briefs
- Legacy backlog field normalization (idea -> title, potential_hook -> hook)
- Legacy backlog status normalization (in_production, published)
- Missing or partial persisted data recovery
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from cc_deep_research.content_gen.backlog_service import _normalize_backlog_patch
from cc_deep_research.content_gen.models import BacklogItem, BacklogOutput
from cc_deep_research.content_gen.storage import BacklogStore, SqliteBacklogStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def yaml_backlog_store(temp_dir: Path) -> BacklogStore:
    """Return a BacklogStore backed by a temp YAML file."""
    path = temp_dir / "backlog.yaml"
    return BacklogStore(path)


@pytest.fixture
def sqlite_backlog_store(temp_dir: Path) -> SqliteBacklogStore:
    """Return a SqliteBacklogStore backed by a temp SQLite file."""
    db_path = temp_dir / "backlog.db"
    return SqliteBacklogStore(path=db_path)


# ---------------------------------------------------------------------------
# YAML-to-SQLite Migration Tests (Backlog)
# ---------------------------------------------------------------------------


def test_sqlite_backlog_store_empty_load(temp_dir: Path) -> None:
    """SqliteBacklogStore.load() returns empty output when DB is empty and no YAML."""
    yaml_path = temp_dir / "nonexistent.yaml"
    store = SqliteBacklogStore(path=temp_dir / "empty.db", yaml_store_path=yaml_path)
    output = store.load()
    assert isinstance(output, BacklogOutput)
    assert output.items == []


def test_sqlite_backlog_store_yaml_import(temp_dir: Path) -> None:
    """SqliteBacklogStore loads from YAML when SQLite is empty."""
    yaml_path = temp_dir / "backlog.yaml"
    yaml_path.write_text(
        yaml.dump({
            "items": [
                {
                    "idea_id": "yaml_idea_001",
                    "category": "authority-building",
                    "title": "YAML Imported Idea",
                    "audience": "SaaS founders",
                    "problem": "premium tiers feel arbitrary",
                    "hook": "Your enterprise tier may only exist to make pro look cheap",
                    "content_type": "teardown",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ]
        })
    )

    db_path = temp_dir / "backlog.db"
    store = SqliteBacklogStore(path=db_path, yaml_store_path=yaml_path)

    output = store.load()
    assert len(output.items) == 1
    assert output.items[0].idea_id == "yaml_idea_001"
    assert output.items[0].title == "YAML Imported Idea"


def test_sqlite_backlog_store_yaml_import_loads_all_items(temp_dir: Path) -> None:
    """SqliteBacklogStore loads all items from YAML including those with empty idea_id.

    Unlike SqliteBriefStore, SqliteBacklogStore does not filter out items with
    empty idea_id during YAML import - it persists them as-is.
    """
    yaml_path = temp_dir / "backlog.yaml"
    yaml_path.write_text(
        yaml.dump({
            "items": [
                {
                    "idea_id": "valid_idea",
                    "category": "authority-building",
                    "title": "Valid Idea",
                    "audience": "SaaS founders",
                    "problem": "premium tiers feel arbitrary",
                    "hook": "Test hook",
                    "content_type": "teardown",
                },
                {
                    "idea_id": "",
                    "category": "authority-building",
                    "title": "Empty idea_id Idea",
                    "audience": "SaaS founders",
                    "problem": "premium tiers feel arbitrary",
                    "hook": "Test hook",
                    "content_type": "teardown",
                }
            ]
        })
    )

    db_path = temp_dir / "backlog.db"
    store = SqliteBacklogStore(path=db_path, yaml_store_path=yaml_path)

    output = store.load()
    assert len(output.items) == 2
    idea_ids = {item.idea_id for item in output.items}
    assert "valid_idea" in idea_ids
    assert "" in idea_ids


def test_sqlite_backlog_store_yaml_import_missing_file(temp_dir: Path) -> None:
    """SqliteBacklogStore handles missing YAML file gracefully."""
    db_path = temp_dir / "backlog.db"
    store = SqliteBacklogStore(path=db_path, yaml_store_path=temp_dir / "nonexistent.yaml")

    output = store.load()
    assert isinstance(output, BacklogOutput)
    assert output.items == []


def test_sqlite_backlog_store_save_and_load(temp_dir: Path) -> None:
    """SqliteBacklogStore.save() persists items that can be loaded."""
    store = SqliteBacklogStore(path=temp_dir / "test.db")

    item = BacklogItem(
        idea_id="sqlite_idea_001",
        category="authority-building",
        title="SQLite Persisted Idea",
        audience="SaaS founders",
        problem="premium tiers feel arbitrary",
        hook="Your enterprise tier may only exist to make pro look cheap",
        content_type="teardown",
        created_at=datetime.now(tz=UTC).isoformat(),
        updated_at=datetime.now(tz=UTC).isoformat(),
    )
    output = BacklogOutput(items=[item])
    store.save(output)

    loaded = store.load()
    assert len(loaded.items) == 1
    assert loaded.items[0].idea_id == "sqlite_idea_001"
    assert loaded.items[0].title == "SQLite Persisted Idea"


def test_sqlite_backlog_store_update_item(temp_dir: Path) -> None:
    """SqliteBacklogStore.update_item() applies partial updates."""
    store = SqliteBacklogStore(path=temp_dir / "test.db")

    item = BacklogItem(
        idea_id="update_idea_001",
        category="authority-building",
        title="Original Title",
        audience="SaaS founders",
        problem="premium tiers feel arbitrary",
        hook="Original hook",
        content_type="teardown",
        created_at=datetime.now(tz=UTC).isoformat(),
        updated_at=datetime.now(tz=UTC).isoformat(),
    )
    store.save(BacklogOutput(items=[item]))

    updated = store.update_item("update_idea_001", {"title": "Updated Title"})
    assert updated is not None
    assert updated.title == "Updated Title"
    assert updated.idea_id == "update_idea_001"


# ---------------------------------------------------------------------------
# Legacy Field Normalization Tests
# ---------------------------------------------------------------------------


def test_normalize_backlog_patch_idea_to_title() -> None:
    """_normalize_backlog_patch maps legacy 'idea' key to 'title'."""
    patch = {"idea": "Legacy idea text"}
    normalized = _normalize_backlog_patch(patch)
    assert normalized.get("title") == "Legacy idea text"
    assert "idea" not in normalized


def test_normalize_backlog_patch_idea_does_not_override_title() -> None:
    """_normalize_backlog_patch does not override existing title with 'idea'."""
    patch = {"idea": "Legacy idea", "title": "Canonical title"}
    normalized = _normalize_backlog_patch(patch)
    assert normalized.get("title") == "Canonical title"
    assert "idea" not in normalized


def test_normalize_backlog_patch_potential_hook_to_hook() -> None:
    """_normalize_backlog_patch maps legacy 'potential_hook' key to 'hook'."""
    patch = {"potential_hook": "Legacy hook text"}
    normalized = _normalize_backlog_patch(patch)
    assert normalized.get("hook") == "Legacy hook text"
    assert "potential_hook" not in normalized


def test_normalize_backlog_patch_potential_hook_does_not_override_hook() -> None:
    """_normalize_backlog_patch does not override existing hook with 'potential_hook'."""
    patch = {"potential_hook": "Legacy hook", "hook": "Canonical hook"}
    normalized = _normalize_backlog_patch(patch)
    assert normalized.get("hook") == "Canonical hook"
    assert "potential_hook" not in normalized


def test_normalize_backlog_patch_preserves_other_fields() -> None:
    """_normalize_backlog_patch preserves fields that are not legacy keys."""
    patch = {"title": "Canonical title", "category": "authority-building", "audience": "SaaS founders"}
    normalized = _normalize_backlog_patch(patch)
    assert normalized.get("title") == "Canonical title"
    assert normalized.get("category") == "authority-building"
    assert normalized.get("audience") == "SaaS founders"


# ---------------------------------------------------------------------------
# BacklogItem Legacy Field Tests (model-level)
# ---------------------------------------------------------------------------


def test_backlog_item_legacy_idea_alias() -> None:
    """BacklogItem provides 'idea' as an alias for 'title' via __getattr__."""
    item = BacklogItem(
        idea_id="alias_test",
        title="Canonical title",
        audience="SaaS founders",
        problem="premium tiers feel arbitrary",
        hook="Test hook",
        content_type="teardown",
    )
    assert item.idea == "Canonical title"


def test_backlog_item_legacy_potential_hook_alias() -> None:
    """BacklogItem provides 'potential_hook' as an alias for 'hook' via __getattr__."""
    item = BacklogItem(
        idea_id="alias_test",
        title="Canonical title",
        audience="SaaS founders",
        problem="premium tiers feel arbitrary",
        hook="Canonical hook",
        content_type="teardown",
    )
    assert item.potential_hook == "Canonical hook"


def test_backlog_item_legacy_status_in_production() -> None:
    """BacklogItem.model_validate normalizes legacy 'in_production' status."""
    data = {
        "idea_id": "status_test",
        "title": "Test idea",
        "audience": "SaaS founders",
        "problem": "test problem",
        "hook": "test hook",
        "content_type": "teardown",
        "status": "in_production",
    }
    item = BacklogItem.model_validate(data)
    assert item.production_status == "in_production"


def test_backlog_item_legacy_status_published() -> None:
    """BacklogItem.model_validate normalizes legacy 'published' status."""
    data = {
        "idea_id": "status_test",
        "title": "Test idea",
        "audience": "SaaS founders",
        "problem": "test problem",
        "hook": "test hook",
        "content_type": "teardown",
        "status": "published",
    }
    item = BacklogItem.model_validate(data)
    assert item.production_status == "ready_to_publish"


# ---------------------------------------------------------------------------
# Missing / Partial Data Recovery Tests
# ---------------------------------------------------------------------------


def test_yaml_backlog_store_missing_file_returns_empty(temp_dir: Path) -> None:
    """BacklogStore.load() returns empty BacklogOutput when file is missing."""
    store = BacklogStore(path=temp_dir / "nonexistent.yaml")
    output = store.load()
    assert isinstance(output, BacklogOutput)
    assert output.items == []


def test_yaml_backlog_store_partial_data_recovery(temp_dir: Path) -> None:
    """BacklogStore.load() recovers from partial YAML data."""
    yaml_path = temp_dir / "partial.yaml"
    yaml_path.write_text(
        yaml.dump({
            "items": [
                {
                    "idea_id": "partial_idea",
                    "category": "authority-building",
                    "title": "Partial Idea",
                    "audience": "SaaS founders",
                    "problem": "premium tiers feel arbitrary",
                    "hook": "Test hook",
                    "content_type": "teardown",
                }
            ]
        })
    )
    store = BacklogStore(path=yaml_path)
    output = store.load()
    assert len(output.items) == 1
    assert output.items[0].idea_id == "partial_idea"


def test_yaml_backlog_store_empty_file_returns_empty(temp_dir: Path) -> None:
    """BacklogStore.load() returns empty BacklogOutput when YAML file is empty."""
    yaml_path = temp_dir / "empty.yaml"
    yaml_path.write_text("")
    store = BacklogStore(path=yaml_path)
    output = store.load()
    assert isinstance(output, BacklogOutput)
    assert output.items == []
