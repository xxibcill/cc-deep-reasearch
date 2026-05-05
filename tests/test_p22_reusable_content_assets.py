"""Tests for reusable content assets (P22-T4)."""

from __future__ import annotations

import pytest

from cc_deep_research.content_gen.models import (
    ReusableAsset,
    ReusableAssetType,
    AssetProvenanceLink,
)


class TestReusableAssetModel:
    def test_asset_defaults(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.HOOK_PATTERN,
            name="Strong hook pattern",
            content="Start with the counter-intuitive truth",
        )
        assert asset.asset_type == ReusableAssetType.HOOK_PATTERN
        assert asset.reuse_count == 0
        assert asset.is_popular is False
        assert asset.is_proven is False

    def test_asset_is_popular_threshold(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.HOOK_PATTERN,
            name="Popular hook",
            content="Hook",
            reuse_count=3,
        )
        assert asset.is_popular is True

    def test_asset_is_proven_by_engagement(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.PACKAGING_TEMPLATE,
            name="High eng rate",
            content="Caption",
            engagement_rate=0.08,
        )
        assert asset.is_proven is True

    def test_asset_is_proven_by_views(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.ANGLE_BEAT,
            name="High views",
            content="Angle beat",
            view_count=2000,
        )
        assert asset.is_proven is True

    def test_asset_is_not_proven_without_data(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.ANGLE_BEAT,
            name="New asset",
            content="New content",
        )
        assert asset.is_proven is False

    def test_asset_provenance_fields(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.ARGUMENT_STRUCTURE,
            name="Winning angle",
            content="Thesis for fintech content",
            source_idea_id="idea-001",
            source_run_id="run-001",
            source_brief_id="brief-001",
            source_stage="generate_angles",
            extraction_reason="Winning angle in successful campaign",
            pillar="fintech",
            audience="founders",
            platform="youtube",
            format="short_form_video",
        )
        assert asset.source_idea_id == "idea-001"
        assert asset.source_stage == "generate_angles"
        assert asset.pillar == "fintech"
        assert asset.audience == "founders"


class TestAssetProvenanceLink:
    def test_provenance_link_fields(self) -> None:
        link = AssetProvenanceLink(
            asset_id="ra_abc12345",
            source_idea_id="idea-001",
            source_run_id="run-001",
            source_brief_id="brief-001",
            source_stage="scripting",
            extraction_context="High hook strength",
        )
        assert link.asset_id == "ra_abc12345"
        assert link.source_stage == "scripting"
        assert link.extraction_context == "High hook strength"


class TestReusableAssetTypes:
    def test_all_asset_types_present(self) -> None:
        assert ReusableAssetType.HOOK_PATTERN.value == "hook_pattern"
        assert ReusableAssetType.ANGLE_BEAT.value == "angle_beat"
        assert ReusableAssetType.EVIDENCE_CITATION.value == "evidence_citation"
        assert ReusableAssetType.ARGUMENT_STRUCTURE.value == "argument_structure"
        assert ReusableAssetType.COUNTERARGUMENT.value == "counterargument"
        assert ReusableAssetType.PACKAGING_TEMPLATE.value == "packaging_template"
        assert ReusableAssetType.VISUAL_BEAT.value == "visual_beat"
        assert ReusableAssetType.FULL_BRIEF.value == "full_brief"


class TestReusableAssetStore:
    def test_asset_serialization_round_trip(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.HOOK_PATTERN,
            name="Test hook",
            description="A test hook pattern",
            content="Open with a bold claim",
            source_idea_id="idea-001",
            source_stage="scripting",
            pillar="tech",
            audience="developers",
            platform="youtube",
            format="short_form_video",
            performance_score=7.5,
            engagement_rate=0.06,
            view_count=1500,
        )
        data = asset.model_dump(mode="json")
        restored = ReusableAsset.model_validate(data)
        assert restored.asset_id == asset.asset_id
        assert restored.name == asset.name
        assert restored.source_idea_id == asset.source_idea_id
        assert restored.engagement_rate == asset.engagement_rate

    def test_asset_metadata_passthrough(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.PACKAGING_TEMPLATE,
            name="TikTok caption",
            content="#fyp #tech",
            metadata={
                "used_in_campaign": "Q1_fintech",
                "variant_count": 3,
            },
        )
        assert asset.metadata["used_in_campaign"] == "Q1_fintech"
        assert asset.metadata["variant_count"] == 3

    def test_asset_performance_sorting_fields(self) -> None:
        asset = ReusableAsset(
            asset_type=ReusableAssetType.HOOK_PATTERN,
            name="Performance asset",
            content="Hook",
            performance_score=8.5,
            engagement_rate=0.12,
            view_count=10000,
        )
        assert asset.performance_score == 8.5
        assert asset.engagement_rate == 0.12
        assert asset.view_count == 10000