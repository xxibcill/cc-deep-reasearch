"""Tests for the brief persistence, migration, and service layers.

These tests cover:
- SqliteBriefStore CRUD and YAML import
- BriefRevisionStore storage and retrieval
- BriefService lifecycle transitions and revision management
- BriefMigration from legacy formats
- ConcurrentModificationError behavior
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cc_deep_research.content_gen.brief_migration import BriefMigration
from cc_deep_research.content_gen.brief_service import BriefService, ConcurrentModificationError
from cc_deep_research.content_gen.models import (
    BriefLifecycleState,
    BriefProvenance,
    BriefRevision,
    ManagedBriefOutput,
    ManagedOpportunityBrief,
    OpportunityBrief,
)
from cc_deep_research.content_gen.storage import (
    BriefRevisionStore,
    BriefStore,
    SqliteBriefStore,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def yaml_store(temp_dir: Path) -> BriefStore:
    """Return a BriefStore backed by a temp YAML file."""
    path = temp_dir / "briefs.yaml"
    return BriefStore(path)


@pytest.fixture
def sqlite_store(temp_dir: Path) -> SqliteBriefStore:
    """Return a SqliteBriefStore backed by a temp SQLite file."""
    db_path = temp_dir / "briefs.db"
    return SqliteBriefStore(path=db_path)


@pytest.fixture
def revision_store(temp_dir: Path) -> BriefRevisionStore:
    """Return a BriefRevisionStore backed by a temp SQLite file."""
    db_path = temp_dir / "revisions.db"
    return BriefRevisionStore(path=db_path)


@pytest.fixture
def brief_service(temp_dir: Path) -> BriefService:
    """Return a BriefService with a temp SQLite backend."""
    return BriefService(
        store=SqliteBriefStore(path=temp_dir / "briefs.db"),
        revision_store=BriefRevisionStore(path=temp_dir / "revisions.db"),
    )


def make_opportunity_brief(
    theme: str = "Test Theme",
    goal: str = "Test Goal",
    brief_id: str = "test_001",
) -> OpportunityBrief:
    """Create a minimal OpportunityBrief for testing."""
    return OpportunityBrief(
        brief_id=brief_id,
        theme=theme,
        goal=goal,
        primary_audience_segment="Content creators",
        problem_statements=["Problem 1", "Problem 2"],
        content_objective="Test objective",
        proof_requirements=["Proof 1"],
        platform_constraints=["Constraint 1"],
        risk_constraints=["Risk 1"],
        freshness_rationale="Fresh because",
        sub_angles=["Angle 1", "Angle 2"],
        research_hypotheses=["Hypothesis 1"],
        success_criteria=["Criterion 1"],
        expert_take="Expert insight",
        non_obvious_claims_to_test=["Claim 1"],
        genericity_risks=["Risk 1"],
        is_generated=True,
    )


def make_revision(
    brief_id: str,
    version: int = 1,
    theme: str = "Test Theme",
) -> BriefRevision:
    """Create a BriefRevision for testing."""
    return BriefRevision(
        brief_id=brief_id,
        version=version,
        theme=theme,
        goal="Test Goal",
        primary_audience_segment="Test Audience",
        secondary_audience_segments=["Audience 2"],
        problem_statements=["Problem 1"],
        content_objective="Test objective",
        proof_requirements=["Proof 1"],
        platform_constraints=["Platform constraint"],
        risk_constraints=["Risk constraint"],
        freshness_rationale="Fresh rationale",
        sub_angles=["Sub-angle 1"],
        research_hypotheses=["Hypothesis 1"],
        success_criteria=["Success criterion 1"],
        expert_take="Expert take",
        non_obvious_claims_to_test=["Non-obvious claim"],
        genericity_risks=["Genericity risk"],
        provenance=BriefProvenance.GENERATED,
        is_generated=True,
        revision_notes=f"Test revision v{version}",
        source_pipeline_id="test_pipeline",
        created_at=datetime.now(tz=UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# SqliteBriefStore Tests
# ---------------------------------------------------------------------------


def test_sqlite_brief_store_empty_load(temp_dir: Path) -> None:
    """SqliteBriefStore.load() returns empty output when DB is empty and no YAML exists."""
    # Provide explicit yaml_store_path to prevent falling back to user's default YAML
    yaml_path = temp_dir / "nonexistent.yaml"
    store = SqliteBriefStore(path=temp_dir / "empty.db", yaml_store_path=yaml_path)
    output = store.load()
    assert isinstance(output, ManagedBriefOutput)
    assert output.briefs == []


def test_sqlite_brief_store_save_and_load(temp_dir: Path) -> None:
    """SqliteBriefStore.save() persists briefs that can be loaded."""
    store = SqliteBriefStore(path=temp_dir / "test.db")

    brief = ManagedOpportunityBrief(
        brief_id="mbrief_test_1",
        title="Test Brief",
        lifecycle_state=BriefLifecycleState.DRAFT,
        current_revision_id="rev_001",
        latest_revision_id="rev_001",
        revision_count=1,
        provenance=BriefProvenance.GENERATED,
        created_at=datetime.now(tz=UTC).isoformat(),
        updated_at=datetime.now(tz=UTC).isoformat(),
    )

    output = ManagedBriefOutput(briefs=[brief])
    store.save(output)

    loaded = store.load()
    assert len(loaded.briefs) == 1
    assert loaded.briefs[0].brief_id == "mbrief_test_1"
    assert loaded.briefs[0].title == "Test Brief"


def test_sqlite_brief_store_update_brief(temp_dir: Path) -> None:
    """SqliteBriefStore.update_brief() applies partial updates."""
    store = SqliteBriefStore(path=temp_dir / "test.db")

    brief = ManagedOpportunityBrief(
        brief_id="mbrief_test_2",
        title="Original Title",
        lifecycle_state=BriefLifecycleState.DRAFT,
        provenance=BriefProvenance.GENERATED,
        created_at=datetime.now(tz=UTC).isoformat(),
        updated_at=datetime.now(tz=UTC).isoformat(),
    )
    store.save(ManagedBriefOutput(briefs=[brief]))

    updated = store.update_brief("mbrief_test_2", {"title": "Updated Title"})
    assert updated is not None
    assert updated.title == "Updated Title"
    assert updated.brief_id == "mbrief_test_2"  # unchanged


def test_sqlite_brief_store_update_brief_not_found(temp_dir: Path) -> None:
    """SqliteBriefStore.update_brief() returns None for missing brief."""
    store = SqliteBriefStore(path=temp_dir / "test.db")
    result = store.update_brief("nonexistent", {"title": "New Title"})
    assert result is None


def test_sqlite_brief_store_delete_briefs(temp_dir: Path) -> None:
    """SqliteBriefStore.save() removes briefs not in the new output."""
    store = SqliteBriefStore(path=temp_dir / "test.db")

    brief1 = ManagedOpportunityBrief(
        brief_id="mbrief_to_keep",
        title="Keep Me",
        lifecycle_state=BriefLifecycleState.DRAFT,
        provenance=BriefProvenance.GENERATED,
        created_at=datetime.now(tz=UTC).isoformat(),
        updated_at=datetime.now(tz=UTC).isoformat(),
    )
    brief2 = ManagedOpportunityBrief(
        brief_id="mbrief_to_remove",
        title="Remove Me",
        lifecycle_state=BriefLifecycleState.DRAFT,
        provenance=BriefProvenance.GENERATED,
        created_at=datetime.now(tz=UTC).isoformat(),
        updated_at=datetime.now(tz=UTC).isoformat(),
    )
    store.save(ManagedBriefOutput(briefs=[brief1, brief2]))

    # Save only brief1
    store.save(ManagedBriefOutput(briefs=[brief1]))

    loaded = store.load()
    assert len(loaded.briefs) == 1
    assert loaded.briefs[0].brief_id == "mbrief_to_keep"


def test_sqlite_brief_store_yaml_import(temp_dir: Path) -> None:
    """SqliteBriefStore loads from YAML when SQLite is empty."""
    yaml_path = temp_dir / "briefs.yaml"
    # Use lowercase enum values to match Pydantic model validation
    yaml_path.write_text(
        """
briefs:
  - brief_id: mbrief_yaml_001
    title: YAML Imported Brief
    lifecycle_state: draft
    provenance: imported
    created_at: "2024-01-01T00:00:00Z"
    updated_at: "2024-01-01T00:00:00Z"
"""
    )

    # Create sqlite store pointing to same directory (different file)
    db_path = temp_dir / "briefs.db"
    store = SqliteBriefStore(path=db_path, yaml_store_path=yaml_path)

    # First load triggers import
    output = store.load()
    assert len(output.briefs) == 1
    assert output.briefs[0].brief_id == "mbrief_yaml_001"
    assert output.briefs[0].title == "YAML Imported Brief"


def test_sqlite_brief_store_yaml_import_skips_malformed(temp_dir: Path) -> None:
    """SqliteBriefStore skips briefs with empty brief_id during YAML import."""
    yaml_path = temp_dir / "briefs.yaml"
    # Use lowercase enum values and valid entries; the second has empty brief_id and gets skipped
    yaml_path.write_text(
        """
briefs:
  - brief_id: mbrief_valid
    title: Valid Brief
    lifecycle_state: draft
    provenance: imported
  - brief_id: ""
    title: Invalid Brief
    lifecycle_state: draft
    provenance: imported
"""
    )

    db_path = temp_dir / "briefs.db"
    store = SqliteBriefStore(path=db_path, yaml_store_path=yaml_path)

    output = store.load()
    assert len(output.briefs) == 1
    assert output.briefs[0].brief_id == "mbrief_valid"


def test_sqlite_brief_store_yaml_import_missing_file(temp_dir: Path) -> None:
    """SqliteBriefStore handles missing YAML file gracefully."""
    db_path = temp_dir / "briefs.db"
    store = SqliteBriefStore(path=db_path, yaml_store_path=temp_dir / "nonexistent.yaml")

    output = store.load()
    assert isinstance(output, ManagedBriefOutput)
    assert output.briefs == []


# ---------------------------------------------------------------------------
# BriefRevisionStore Tests
# ---------------------------------------------------------------------------


def test_revision_store_save_and_get(revision_store: BriefRevisionStore) -> None:
    """BriefRevisionStore persists and retrieves revisions."""
    rev = make_revision("mbrief_test_1", version=1)
    revision_store.save_revision(rev)

    loaded = revision_store.get_revision(rev.revision_id)
    assert loaded is not None
    assert loaded.brief_id == "mbrief_test_1"
    assert loaded.version == 1
    assert loaded.theme == "Test Theme"


def test_revision_store_get_not_found(revision_store: BriefRevisionStore) -> None:
    """BriefRevisionStore.get_revision() returns None for missing revision."""
    result = revision_store.get_revision("nonexistent_revision")
    assert result is None


def test_revision_store_list_revisions(revision_store: BriefRevisionStore) -> None:
    """BriefRevisionStore.list_revisions() returns revisions in reverse order."""
    brief_id = "mbrief_test_list"
    for i in range(1, 4):
        rev = make_revision(brief_id, version=i, theme=f"Theme v{i}")
        revision_store.save_revision(rev)

    revisions = revision_store.list_revisions(brief_id)
    assert len(revisions) == 3
    # Most recent first
    assert revisions[0].version == 3
    assert revisions[1].version == 2
    assert revisions[2].version == 1


def test_revision_store_get_latest_revision(revision_store: BriefRevisionStore) -> None:
    """BriefRevisionStore.get_latest_revision() returns the most recent revision."""
    brief_id = "mbrief_test_latest"
    for i in range(1, 4):
        rev = make_revision(brief_id, version=i)
        revision_store.save_revision(rev)

    latest = revision_store.get_latest_revision(brief_id)
    assert latest is not None
    assert latest.version == 3


def test_revision_store_delete_revisions(revision_store: BriefRevisionStore) -> None:
    """BriefRevisionStore.delete_revisions_for_brief() removes all revisions for a brief."""
    brief_id = "mbrief_test_delete"
    for i in range(1, 4):
        rev = make_revision(brief_id, version=i)
        revision_store.save_revision(rev)

    count = revision_store.delete_revisions_for_brief(brief_id)
    assert count == 3

    remaining = revision_store.list_revisions(brief_id)
    assert len(remaining) == 0


# ---------------------------------------------------------------------------
# BriefService Tests
# ---------------------------------------------------------------------------


def test_brief_service_create_from_opportunity(brief_service: BriefService) -> None:
    """BriefService.create_from_opportunity() creates a managed brief with initial revision."""
    opp = make_opportunity_brief(theme="Service Test Theme", brief_id="svc_001")

    managed = brief_service.create_from_opportunity(
        opp,
        provenance=BriefProvenance.GENERATED,
        source_pipeline_id="test_pipeline",
        revision_notes="Initial creation",
    )

    assert managed is not None
    assert managed.brief_id.startswith("mbrief_")
    assert managed.title == "Service Test Theme"
    assert managed.lifecycle_state == BriefLifecycleState.DRAFT
    assert managed.revision_count == 1

    # Check revision was created
    revision = brief_service.get_revision(managed.current_revision_id)
    assert revision is not None
    assert revision.theme == "Service Test Theme"


def test_brief_service_save_revision(brief_service: BriefService) -> None:
    """BriefService.save_revision() creates a new revision without changing head."""
    opp1 = make_opportunity_brief(brief_id="rev_test_001")
    managed = brief_service.create_from_opportunity(opp1, revision_notes="Initial")

    original_head = managed.current_revision_id
    original_count = managed.revision_count

    # Save a new revision
    opp2 = make_opportunity_brief(brief_id="rev_test_001", theme="Updated Theme")
    revision = brief_service.save_revision(
        managed.brief_id,
        opp2,
        revision_notes="Second revision",
    )

    assert revision is not None
    assert revision.version == 2
    assert revision.theme == "Updated Theme"

    # Head should not have changed
    updated = brief_service.get_brief(managed.brief_id)
    assert updated is not None
    assert updated.current_revision_id == original_head
    assert updated.revision_count == original_count + 1


def test_brief_service_update_head(brief_service: BriefService) -> None:
    """BriefService.update_head() changes the current revision pointer."""
    opp1 = make_opportunity_brief(brief_id="head_test_001")
    managed = brief_service.create_from_opportunity(opp1, revision_notes="Initial")

    # Save a new revision
    opp2 = make_opportunity_brief(brief_id="head_test_001", theme="New Head Theme")
    revision = brief_service.save_revision(managed.brief_id, opp2, revision_notes="Second")

    # Update head to the new revision
    updated = brief_service.update_head(managed.brief_id, revision.revision_id)

    assert updated is not None
    assert updated.current_revision_id == revision.revision_id


def test_brief_service_approve(brief_service: BriefService) -> None:
    """BriefService.approve() transitions a brief to APPROVED state."""
    opp = make_opportunity_brief(brief_id="approve_test")
    managed = brief_service.create_from_opportunity(opp)

    assert managed.lifecycle_state == BriefLifecycleState.DRAFT

    approved = brief_service.approve(managed.brief_id)
    assert approved is not None
    assert approved.lifecycle_state == BriefLifecycleState.APPROVED


def test_brief_service_archive(brief_service: BriefService) -> None:
    """BriefService.archive() transitions a brief to ARCHIVED state."""
    opp = make_opportunity_brief(brief_id="archive_test")
    managed = brief_service.create_from_opportunity(opp)
    approved = brief_service.approve(managed.brief_id)

    archived = brief_service.archive(approved.brief_id)
    assert archived is not None
    assert archived.lifecycle_state == BriefLifecycleState.ARCHIVED


def test_brief_service_supersede(brief_service: BriefService) -> None:
    """BriefService.supersede() transitions a brief to SUPERSEDED state."""
    opp = make_opportunity_brief(brief_id="supersede_test")
    managed = brief_service.create_from_opportunity(opp)
    brief_service.approve(managed.brief_id)

    superseded = brief_service.supersede(managed.brief_id)
    assert superseded is not None
    assert superseded.lifecycle_state == BriefLifecycleState.SUPERSEDED


def test_brief_service_revert_to_draft(brief_service: BriefService) -> None:
    """BriefService.revert_to_draft() transitions an APPROVED brief back to DRAFT."""
    opp = make_opportunity_brief(brief_id="revert_test")
    managed = brief_service.create_from_opportunity(opp)
    brief_service.approve(managed.brief_id)

    reverted = brief_service.revert_to_draft(managed.brief_id)
    assert reverted is not None
    assert reverted.lifecycle_state == BriefLifecycleState.DRAFT


def test_brief_service_concurrent_modification_error(temp_dir: Path) -> None:
    """BriefService raises ConcurrentModificationError on stale updated_at."""
    store = SqliteBriefStore(path=temp_dir / "concurrent.db")
    revision_store = BriefRevisionStore(path=temp_dir / "rev_concurrent.db")
    service = BriefService(store=store, revision_store=revision_store)

    opp = make_opportunity_brief(brief_id="conc_test")
    managed = service.create_from_opportunity(opp)

    # Try to update with a wrong expected_updated_at
    with pytest.raises(ConcurrentModificationError):
        service.update_brief(
            managed.brief_id,
            {"title": "New Title"},
            expected_updated_at="1970-01-01T00:00:00Z",  # Wrong timestamp
        )


def test_brief_service_clone_brief(brief_service: BriefService) -> None:
    """BriefService.clone_brief() creates an independent copy."""
    opp = make_opportunity_brief(brief_id="clone_test", theme="Clone Source Theme")
    managed = brief_service.create_from_opportunity(opp)
    brief_service.approve(managed.brief_id)

    cloned = brief_service.clone_brief(managed.brief_id, new_title="Cloned Title")

    assert cloned is not None
    assert cloned.brief_id != managed.brief_id
    assert cloned.title == "Cloned Title"
    assert cloned.provenance == BriefProvenance.CLONED
    assert cloned.source_brief_id == ""
    assert cloned.lifecycle_state == BriefLifecycleState.DRAFT


def test_brief_service_branch_brief(brief_service: BriefService) -> None:
    """BriefService.branch_brief() creates a derivative with lineage tracking."""
    opp = make_opportunity_brief(brief_id="branch_test", theme="Branch Source Theme")
    managed = brief_service.create_from_opportunity(opp)

    branched = brief_service.branch_brief(
        managed.brief_id,
        new_title="Branched Title",
        branch_reason="Testing for different channel",
    )

    assert branched is not None
    assert branched.brief_id != managed.brief_id
    assert branched.title == "Branched Title"
    assert branched.provenance == BriefProvenance.BRANCHED
    assert branched.source_brief_id == managed.brief_id
    assert branched.branch_reason == "Testing for different channel"


def test_brief_service_list_siblings(brief_service: BriefService) -> None:
    """BriefService.list_sibling_briefs() returns briefs branched from the same source."""
    opp = make_opportunity_brief(brief_id="sibling_test")
    managed = brief_service.create_from_opportunity(opp)

    branch1 = brief_service.branch_brief(managed.brief_id, new_title="Branch 1")
    branch2 = brief_service.branch_brief(managed.brief_id, new_title="Branch 2")

    siblings = brief_service.list_sibling_briefs(branch1.brief_id)
    assert len(siblings) == 1
    assert siblings[0].brief_id == branch2.brief_id


def test_brief_service_update_brief_title(brief_service: BriefService) -> None:
    """BriefService.update_brief() allows updating mutable fields."""
    opp = make_opportunity_brief(brief_id="update_test")
    managed = brief_service.create_from_opportunity(opp)

    updated = brief_service.update_brief(managed.brief_id, {"title": "New Title"})
    assert updated is not None
    assert updated.title == "New Title"


def test_brief_service_update_brief_rejects_unsafe_fields(brief_service: BriefService) -> None:
    """BriefService.update_brief() rejects patches to immutable fields."""
    opp = make_opportunity_brief(brief_id="unsafe_test")
    managed = brief_service.create_from_opportunity(opp)

    # current_revision_id is immutable - must use update_head() instead
    with pytest.raises(ValueError, match="cannot be patched"):
        brief_service.update_brief(
            managed.brief_id,
            {"current_revision_id": "some_other_revision"},  # Should use update_head()
        )


def test_brief_service_get_brief_not_found(brief_service: BriefService) -> None:
    """BriefService.get_brief() returns None for nonexistent brief."""
    result = brief_service.get_brief("nonexistent_brief")
    assert result is None


def test_brief_service_list_revisions(brief_service: BriefService) -> None:
    """BriefService.list_revisions() returns all revisions for a brief."""
    opp = make_opportunity_brief(brief_id="list_rev_test")
    managed = brief_service.create_from_opportunity(opp)

    # create_from_opportunity creates 1 initial revision, then we save 3 more = 4 total
    for i in range(3):
        opp_next = make_opportunity_brief(brief_id="list_rev_test", theme=f"Theme v{i+1}")
        brief_service.save_revision(managed.brief_id, opp_next, revision_notes=f"Revision {i+1}")

    revisions = brief_service.list_revisions(managed.brief_id)
    assert len(revisions) == 4


# ---------------------------------------------------------------------------
# BriefMigration Tests
# ---------------------------------------------------------------------------


def test_brief_migration_from_opportunity_brief() -> None:
    """BriefMigration.from_opportunity_brief() converts legacy brief format."""
    opp = make_opportunity_brief(brief_id="legacy_001", theme="Legacy Theme")
    opp.is_generated = False

    result = BriefMigration.from_opportunity_brief(
        opp,
        provenance=BriefProvenance.IMPORTED,
        source_pipeline_id="legacy_pipeline_123",
    )

    assert result.brief is not None
    assert result.revision is not None
    assert result.brief.brief_id.startswith("mbrief_")
    assert result.brief.lifecycle_state == BriefLifecycleState.DRAFT
    assert result.revision.theme == "Legacy Theme"
    assert result.revision.provenance == BriefProvenance.IMPORTED


def test_brief_migration_with_synthetic_id() -> None:
    """BriefMigration generates a synthetic brief_id when none provided."""
    opp = OpportunityBrief(
        brief_id="",  # No brief_id
        theme="No-ID Theme",
        goal="Goal",
    )

    result = BriefMigration.from_opportunity_brief(opp)

    assert result.brief is not None
    assert result.is_synthetic_revision is True
    assert result.original_brief_id == ""


def test_brief_migration_from_pipeline_context() -> None:
    """BriefMigration.from_pipeline_context() extracts brief from context-like object."""
    opp = make_opportunity_brief(brief_id="ctx_test", theme="Context Theme")

    class MockContext:
        opportunity_brief: OpportunityBrief = opp

    result = BriefMigration.from_pipeline_context(
        MockContext(),
        source_pipeline_id="test_ctx_pipeline",
    )

    assert result.brief is not None
    assert result.revision is not None
    assert result.revision.theme == "Context Theme"


def test_brief_migration_no_brief_in_context() -> None:
    """BriefMigration.from_pipeline_context() handles missing brief gracefully."""

    class EmptyContext:
        pass

    result = BriefMigration.from_pipeline_context(EmptyContext())

    assert result.brief is None
    assert result.revision is None
    assert "No opportunity_brief" in result.migration_notes


def test_brief_migration_build_summary() -> None:
    """BriefMigration.build_migration_summary() aggregates multiple results."""
    opp1 = make_opportunity_brief(brief_id="sum_test_1")
    opp2 = make_opportunity_brief(brief_id="sum_test_2")

    results = [
        BriefMigration.from_opportunity_brief(opp1),
        BriefMigration.from_opportunity_brief(opp2, override_brief_id="mbrief_override"),
    ]

    summary = BriefMigration.build_migration_summary(results)

    assert summary["total"] == 2
    assert summary["successful"] == 2
    assert summary["failed"] == 0


# ---------------------------------------------------------------------------
# Orchestrator Integration (brief resolution) Tests
# ---------------------------------------------------------------------------


def test_orchestrator_resolve_brief_inline_fallback(temp_dir: Path) -> None:
    """Orchestrator falls back to inline snapshot when brief_id is not provided."""
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    config = Config()
    orch = ContentGenOrchestrator(config)

    opp = make_opportunity_brief(theme="Inline Fallback Theme")
    ref, resolved = orch.get_brief_for_run(brief_id=None, snapshot=opp)

    assert ref is not None
    assert ref.reference_type == "inline_fallback"
    assert ref.brief_id == ""
    assert resolved == opp


def test_orchestrator_resolve_brief_not_found_uses_snapshot(
    temp_dir: Path,
) -> None:
    """Orchestrator uses inline snapshot when brief_id doesn't exist in store."""
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    config = Config()
    orch = ContentGenOrchestrator(config)

    opp = make_opportunity_brief(theme="Missing Brief Theme")
    ref, resolved = orch.get_brief_for_run(brief_id="nonexistent_brief", snapshot=opp)

    assert ref is not None
    assert ref.reference_type == "inline_fallback"
    assert resolved == opp
