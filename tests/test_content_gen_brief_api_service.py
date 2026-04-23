"""Tests for the BriefApiService HTTP-layer service.

These tests cover:
- BriefApiService lifecycle transitions
- BriefApiService CRUD operations
- BriefApiService error handling (not found, concurrent modification, validation)
- BriefApiService serialization
- Compare, sibling, clone, branch operations
"""

from __future__ import annotations

import pytest

from cc_deep_research.content_gen.brief_api_service import (
    BriefApiService,
    BriefConcurrentModificationError,
    BriefNotFoundError,
    BriefValidationError,
)
from cc_deep_research.content_gen.models import (
    BriefLifecycleState,
    BriefProvenance,
    OpportunityBrief,
)
from cc_deep_research.content_gen.storage import (
    AuditStore,
    BriefRevisionStore,
    SqliteBriefStore,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def brief_api_service(tmp_path) -> BriefApiService:
    """Return a BriefApiService with fresh temp backends."""
    store = SqliteBriefStore(
        path=tmp_path / "briefs.db",
        yaml_store_path=tmp_path / "nonexistent_briefs.yaml",
    )
    revision_store = BriefRevisionStore(path=tmp_path / "revisions.db")
    audit_store = AuditStore(path=tmp_path / "audit")
    from cc_deep_research.content_gen.brief_service import BriefService
    brief_service = BriefService(store=store, revision_store=revision_store)
    return BriefApiService(
        brief_service=brief_service,
        audit_store=audit_store,
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


# ---------------------------------------------------------------------------
# List / Get Tests
# ---------------------------------------------------------------------------


def test_brief_api_list_briefs_empty(brief_api_service: BriefApiService) -> None:
    """BriefApiService.list_briefs() returns empty list when no briefs exist."""
    result = brief_api_service.list_briefs()
    assert result.items == []
    assert result.count == 0


def test_brief_api_list_briefs_with_filter(brief_api_service: BriefApiService) -> None:
    """BriefApiService.list_briefs() filters by lifecycle state."""
    opp = make_opportunity_brief(theme="Filter Test")
    managed = brief_api_service.create_brief(opp.model_dump())
    brief_api_service.approve_brief(managed.brief_id)

    opp2 = make_opportunity_brief(brief_id="draft_test", theme="Draft Test")
    brief_api_service.create_brief(opp2.model_dump())

    result_all = brief_api_service.list_briefs()
    assert result_all.count == 2

    result_approved = brief_api_service.list_briefs(lifecycle_state="approved")
    assert result_approved.count == 1
    assert result_approved.items[0].lifecycle_state == BriefLifecycleState.APPROVED

    result_draft = brief_api_service.list_briefs(lifecycle_state="draft")
    assert result_draft.count == 1
    assert result_draft.items[0].lifecycle_state == BriefLifecycleState.DRAFT


def test_brief_api_list_briefs_invalid_state(brief_api_service: BriefApiService) -> None:
    """BriefApiService.list_briefs() raises BriefValidationError for invalid state."""
    with pytest.raises(BriefValidationError, match="Invalid lifecycle_state"):
        brief_api_service.list_briefs(lifecycle_state="invalid_state")


def test_brief_api_get_brief_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.get_brief() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.get_brief("nonexistent_brief")


def test_brief_api_get_brief_with_revision(brief_api_service: BriefApiService) -> None:
    """BriefApiService.get_brief_with_revision() returns brief and revision."""
    opp = make_opportunity_brief(theme="With Revision Test")
    managed = brief_api_service.create_brief(opp.model_dump())

    fetched, revision = brief_api_service.get_brief_with_revision(managed.brief_id)
    assert fetched.brief_id == managed.brief_id
    assert revision is not None
    assert revision.brief_id == managed.brief_id


# ---------------------------------------------------------------------------
# Create / Update Tests
# ---------------------------------------------------------------------------


def test_brief_api_create_brief(brief_api_service: BriefApiService) -> None:
    """BriefApiService.create_brief() creates a managed brief."""
    brief_data = make_opportunity_brief(theme="API Create Test").model_dump()
    managed = brief_api_service.create_brief(brief_data)
    assert managed is not None
    assert managed.title == "API Create Test"
    assert managed.lifecycle_state == BriefLifecycleState.DRAFT
    assert managed.revision_count == 1


def test_brief_api_update_brief_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.update_brief() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.update_brief("nonexistent", {"title": "New Title"})


def test_brief_api_update_brief_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.update_brief() updates brief metadata."""
    opp = make_opportunity_brief(brief_id="update_api_test")
    managed = brief_api_service.create_brief(opp.model_dump())

    updated = brief_api_service.update_brief(managed.brief_id, {"title": "Updated Title"})
    assert updated.title == "Updated Title"


def test_brief_api_update_brief_concurrent_modification(brief_api_service: BriefApiService) -> None:
    """BriefApiService.update_brief() raises ConcurrentModificationError on stale timestamp."""
    opp = make_opportunity_brief(brief_id="conc_api_test")
    managed = brief_api_service.create_brief(opp.model_dump())

    with pytest.raises(BriefConcurrentModificationError):
        brief_api_service.update_brief(
            managed.brief_id,
            {"title": "New Title"},
            expected_updated_at="1970-01-01T00:00:00Z",
        )


# ---------------------------------------------------------------------------
# Lifecycle Transition Tests
# ---------------------------------------------------------------------------


def test_brief_api_approve_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.approve_brief() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.approve_brief("nonexistent")


def test_brief_api_approve_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.approve_brief() transitions brief to APPROVED."""
    opp = make_opportunity_brief(brief_id="approve_api_test")
    managed = brief_api_service.create_brief(opp.model_dump())

    approved = brief_api_service.approve_brief(managed.brief_id)
    assert approved.lifecycle_state == BriefLifecycleState.APPROVED


def test_brief_api_archive_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.archive_brief() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.archive_brief("nonexistent")


def test_brief_api_archive_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.archive_brief() transitions brief to ARCHIVED."""
    opp = make_opportunity_brief(brief_id="archive_api_test")
    managed = brief_api_service.create_brief(opp.model_dump())
    brief_api_service.approve_brief(managed.brief_id)

    archived = brief_api_service.archive_brief(managed.brief_id)
    assert archived.lifecycle_state == BriefLifecycleState.ARCHIVED


def test_brief_api_supersede_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.supersede_brief() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.supersede_brief("nonexistent")


def test_brief_api_supersede_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.supersede_brief() transitions brief to SUPERSEDED."""
    opp = make_opportunity_brief(brief_id="supersede_api_test")
    managed = brief_api_service.create_brief(opp.model_dump())
    brief_api_service.approve_brief(managed.brief_id)

    superseded = brief_api_service.supersede_brief(managed.brief_id)
    assert superseded.lifecycle_state == BriefLifecycleState.SUPERSEDED


def test_brief_api_revert_to_draft_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.revert_to_draft() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.revert_to_draft("nonexistent")


def test_brief_api_revert_to_draft_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.revert_to_draft() transitions APPROVED brief back to DRAFT."""
    opp = make_opportunity_brief(brief_id="revert_api_test")
    managed = brief_api_service.create_brief(opp.model_dump())
    brief_api_service.approve_brief(managed.brief_id)

    reverted = brief_api_service.revert_to_draft(managed.brief_id)
    assert reverted.lifecycle_state == BriefLifecycleState.DRAFT


# ---------------------------------------------------------------------------
# Revision Management Tests
# ---------------------------------------------------------------------------


def test_brief_api_save_revision_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.save_revision() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.save_revision("nonexistent", make_opportunity_brief().model_dump())


def test_brief_api_save_revision_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.save_revision() creates a new revision without changing head."""
    opp1 = make_opportunity_brief(brief_id="rev_api_test")
    managed = brief_api_service.create_brief(opp1.model_dump())
    original_head = managed.current_revision_id

    opp2 = make_opportunity_brief(brief_id="rev_api_test", theme="Updated Theme")
    revision = brief_api_service.save_revision(managed.brief_id, opp2.model_dump())

    assert revision is not None
    assert revision.version == 2
    assert revision.theme == "Updated Theme"

    # Head should not have changed
    updated = brief_api_service.get_brief(managed.brief_id)
    assert updated.current_revision_id == original_head


def test_brief_api_update_head_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.update_head() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.update_head("nonexistent", "some_revision_id")


def test_brief_api_update_head_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.update_head() changes the current revision pointer."""
    opp1 = make_opportunity_brief(brief_id="head_api_test")
    managed = brief_api_service.create_brief(opp1.model_dump())

    opp2 = make_opportunity_brief(brief_id="head_api_test", theme="New Head Theme")
    new_revision = brief_api_service.save_revision(
        managed.brief_id, opp2.model_dump(), revision_notes="Second"
    )

    updated = brief_api_service.update_head(managed.brief_id, new_revision.revision_id)
    assert updated.current_revision_id == new_revision.revision_id


def test_brief_api_list_revisions_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.list_revisions() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.list_revisions("nonexistent")


def test_brief_api_list_revisions_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.list_revisions() returns all revisions for a brief."""
    opp = make_opportunity_brief(brief_id="list_rev_api_test")
    managed = brief_api_service.create_brief(opp.model_dump())

    for i in range(3):
        opp_next = make_opportunity_brief(brief_id="list_rev_api_test", theme=f"Theme v{i+1}")
        brief_api_service.save_revision(managed.brief_id, opp_next.model_dump())

    revisions = brief_api_service.list_revisions(managed.brief_id)
    assert len(revisions) == 4  # 1 initial + 3 saved


# ---------------------------------------------------------------------------
# Clone / Branch Tests
# ---------------------------------------------------------------------------


def test_brief_api_clone_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.clone_brief() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.clone_brief("nonexistent")


def test_brief_api_clone_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.clone_brief() creates an independent copy."""
    opp = make_opportunity_brief(brief_id="clone_api_test", theme="Clone Source")
    managed = brief_api_service.create_brief(opp.model_dump())
    brief_api_service.approve_brief(managed.brief_id)

    cloned = brief_api_service.clone_brief(managed.brief_id, new_title="Cloned Title")

    assert cloned is not None
    assert cloned.brief_id != managed.brief_id
    assert cloned.title == "Cloned Title"
    assert cloned.provenance == BriefProvenance.CLONED
    assert cloned.lifecycle_state == BriefLifecycleState.DRAFT


def test_brief_api_branch_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.branch_brief() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.branch_brief("nonexistent")


def test_brief_api_branch_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.branch_brief() creates a derivative with lineage tracking."""
    opp = make_opportunity_brief(brief_id="branch_api_test", theme="Branch Source")
    managed = brief_api_service.create_brief(opp.model_dump())

    branched = brief_api_service.branch_brief(
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


# ---------------------------------------------------------------------------
# Sibling / Compare Tests
# ---------------------------------------------------------------------------


def test_brief_api_list_siblings_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.list_sibling_briefs() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.list_sibling_briefs("nonexistent")


def test_brief_api_list_siblings_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.list_sibling_briefs() returns siblings including source."""
    opp = make_opportunity_brief(brief_id="sibling_api_test")
    managed = brief_api_service.create_brief(opp.model_dump())

    branch1 = brief_api_service.branch_brief(managed.brief_id, new_title="Branch 1")
    branch2 = brief_api_service.branch_brief(managed.brief_id, new_title="Branch 2")

    siblings = brief_api_service.list_sibling_briefs(branch1.brief_id)
    # Should include: source brief, branch2 (sibling of branch1)
    assert len(siblings) == 2
    source = next(b for b in siblings if b.brief_id == managed.brief_id)
    assert source is not None
    other_branch = next(b for b in siblings if b.brief_id == branch2.brief_id)
    assert other_branch is not None


def test_brief_api_compare_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.compare_briefs() raises BriefNotFoundError when one brief is missing."""
    opp = make_opportunity_brief(brief_id="compare_test")
    managed = brief_api_service.create_brief(opp.model_dump())

    with pytest.raises(BriefNotFoundError):
        brief_api_service.compare_briefs(managed.brief_id, "nonexistent")


def test_brief_api_compare_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.compare_briefs() returns both briefs with revisions."""
    opp1 = make_opportunity_brief(brief_id="compare_a", theme="Brief A")
    managed1 = brief_api_service.create_brief(opp1.model_dump())

    opp2 = make_opportunity_brief(brief_id="compare_b", theme="Brief B")
    managed2 = brief_api_service.create_brief(opp2.model_dump())

    brief_a, rev_a, brief_b, rev_b = brief_api_service.compare_briefs(
        managed1.brief_id, managed2.brief_id
    )

    assert brief_a.brief_id == managed1.brief_id
    assert brief_b.brief_id == managed2.brief_id
    assert rev_a is not None
    assert rev_b is not None


# ---------------------------------------------------------------------------
# Serialization Tests
# ---------------------------------------------------------------------------


def test_brief_api_serialize_brief(brief_api_service: BriefApiService) -> None:
    """BriefApiService.serialize_brief() returns JSON-compatible dict."""
    opp = make_opportunity_brief(theme="Serialize Test")
    managed = brief_api_service.create_brief(opp.model_dump())

    serialized = brief_api_service.serialize_brief(managed)
    assert isinstance(serialized, dict)
    assert serialized["brief_id"] == managed.brief_id
    assert serialized["title"] == "Serialize Test"


def test_brief_api_serialize_list(brief_api_service: BriefApiService) -> None:
    """BriefApiService.serialize_list() returns properly shaped response."""
    opp = make_opportunity_brief(theme="List Serialize Test")
    brief_api_service.create_brief(opp.model_dump())

    result = brief_api_service.list_briefs()
    serialized = brief_api_service.serialize_list(result)

    assert "items" in serialized
    assert "count" in serialized
    assert serialized["count"] == 1


def test_brief_api_serialize_brief_with_revision(brief_api_service: BriefApiService) -> None:
    """BriefApiService.serialize_brief_with_revision() includes revision."""
    opp = make_opportunity_brief(theme="With Rev Serialize Test")
    managed = brief_api_service.create_brief(opp.model_dump())
    revision = brief_api_service.get_revision(managed.current_revision_id)

    serialized = brief_api_service.serialize_brief_with_revision(managed, revision)
    assert "current_revision" in serialized
    assert serialized["current_revision"]["theme"] == "With Rev Serialize Test"


# ---------------------------------------------------------------------------
# Audit History Tests
# ---------------------------------------------------------------------------


def test_brief_api_get_audit_history_not_found(brief_api_service: BriefApiService) -> None:
    """BriefApiService.get_audit_history() raises BriefNotFoundError for missing brief."""
    with pytest.raises(BriefNotFoundError):
        brief_api_service.get_audit_history("nonexistent")


def test_brief_api_get_audit_history_success(brief_api_service: BriefApiService) -> None:
    """BriefApiService.get_audit_history() returns audit entries."""
    opp = make_opportunity_brief(brief_id="audit_test")
    managed = brief_api_service.create_brief(opp.model_dump())

    # Audit store should have entries from brief creation
    entries = brief_api_service.get_audit_history(managed.brief_id)
    assert isinstance(entries, list)
