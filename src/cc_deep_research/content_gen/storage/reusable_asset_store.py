"""YAML persistence for reusable content assets."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import ReusableAsset, ReusableAssetType
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path
from cc_deep_research.persistence import atomic_write_text

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _serialize_model_to_dict(model: Any) -> dict[str, Any]:
    """Serialize a Pydantic model to a plain dict, converting enums to string values."""
    from enum import Enum

    def _convert_value(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {k: _convert_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_convert_value(item) for item in value]
        return value

    data = model.model_dump(exclude_none=True)
    return _convert_value(data)


class ReusableAssetStore:
    """Load and save reusable content assets to a YAML file.

    Provides controlled paths for:
    - Storing extracted assets from completed content-gen runs
    - Searching and filtering by audience, pillar, format, platform, performance
    - Provenance tracking back to original source runs
    """

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="reusable_asset_path",
            default_name="reusable_assets.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[ReusableAsset]:
        """Load all reusable assets from disk."""
        if not self._path.exists():
            return []
        data = yaml.safe_load(self._path.read_text()) or {}
        items = data.get("assets", [])
        return [ReusableAsset.model_validate(i) for i in items]

    def save(self, assets: list[ReusableAsset]) -> None:
        """Persist all assets to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "assets": [_serialize_model_to_dict(asset) for asset in assets],
            "last_updated": _now_iso(),
        }
        atomic_write_text(
            self._path,
            yaml.dump(payload, default_flow_style=False, sort_keys=False),
        )

    def add(self, asset: ReusableAsset) -> list[ReusableAsset]:
        """Append an asset and save. Sets created_at and updated_at if empty."""
        if not asset.created_at:
            asset.created_at = _now_iso()
        if not asset.updated_at:
            asset.updated_at = _now_iso()
        assets = self.load()
        assets.append(asset)
        self.save(assets)
        return assets

    def get(self, asset_id: str) -> ReusableAsset | None:
        """Get a single asset by ID."""
        assets = self.load()
        return next((asset for asset in assets if asset.asset_id == asset_id), None)

    def update(self, asset_id: str, updates: dict[str, Any]) -> ReusableAsset | None:
        """Update specific fields of an asset and set updated_at."""
        assets = self.load()
        for i, asset in enumerate(assets):
            if asset.asset_id == asset_id:
                update_data = updates.copy()
                update_data["updated_at"] = _now_iso()
                assets[i] = asset.model_copy(update=update_data)
                self.save(assets)
                return assets[i]
        return None

    def delete(self, asset_id: str) -> bool:
        """Delete an asset by ID. Returns True if deleted."""
        assets = self.load()
        original_count = len(assets)
        assets = [a for a in assets if a.asset_id != asset_id]
        if len(assets) < original_count:
            self.save(assets)
            return True
        return False

    def search(
        self,
        *,
        query: str | None = None,
        asset_type: ReusableAssetType | None = None,
        pillar: str | None = None,
        audience: str | None = None,
        platform: str | None = None,
        format: str | None = None,
        min_performance_score: float | None = None,
        sort_by: str = "updated_at",
        sort_desc: bool = True,
    ) -> list[ReusableAsset]:
        """Search and filter assets by various criteria."""
        assets = self.load()

        if asset_type is not None:
            assets = [a for a in assets if a.asset_type == asset_type]
        if pillar is not None:
            assets = [a for a in assets if a.pillar == pillar]
        if audience is not None:
            assets = [a for a in assets if a.audience == audience]
        if platform is not None:
            assets = [a for a in assets if a.platform == platform]
        if format is not None:
            assets = [a for a in assets if a.format == format]
        if min_performance_score is not None:
            assets = [a for a in assets if a.performance_score >= min_performance_score]

        if query:
            query_lower = query.lower()
            assets = [
                a
                for a in assets
                if query_lower in (a.name or "").lower()
                or query_lower in (a.description or "").lower()
                or query_lower in (a.content or "").lower()
            ]

        # Sort
        sort_key = sort_by if sort_by in {"created_at", "updated_at", "performance_score", "reuse_count", "engagement_rate"} else "updated_at"
        assets.sort(key=lambda a: getattr(a, sort_key, "") or "", reverse=sort_desc)

        return assets

    def get_by_source_idea(self, idea_id: str) -> list[ReusableAsset]:
        """Get all assets extracted from a specific idea."""
        return [asset for asset in self.load() if asset.source_idea_id == idea_id]

    def get_by_source_run(self, run_id: str) -> list[ReusableAsset]:
        """Get all assets extracted from a specific pipeline run."""
        return [asset for asset in self.load() if asset.source_run_id == run_id]

    def record_usage(self, asset_id: str, idea_id: str) -> ReusableAsset | None:
        """Record that an asset was used in a new idea."""
        existing = self.get(asset_id)
        new_reuse_count = (existing.reuse_count if existing else 0) + 1
        return self.update(
            asset_id,
            {
                "reuse_count": new_reuse_count,
                "last_used_at": _now_iso(),
                "last_used_in_idea_id": idea_id,
            },
        )

    def extract_from_scripting(
        self,
        idea_id: str,
        run_id: str,
        brief_id: str,
        hook: str,
        thesis: str,
        engagement_rate: float = 0.0,
        view_count: int = 0,
    ) -> ReusableAsset:
        """Extract a hook pattern asset from completed scripting output."""
        asset = ReusableAsset(
            asset_type=ReusableAssetType.HOOK_PATTERN,
            name=f"Hook: {hook[:50]}",
            description=f"Hook extracted from idea {idea_id}",
            content=hook,
            source_idea_id=idea_id,
            source_run_id=run_id,
            source_brief_id=brief_id,
            source_stage="scripting",
            extraction_reason="High hook strength in successful content",
            performance_score=engagement_rate * 100 if engagement_rate else 0.0,
            engagement_rate=engagement_rate,
            view_count=view_count,
        )
        self.add(asset)
        return asset

    def extract_from_packaging(
        self,
        idea_id: str,
        run_id: str,
        brief_id: str,
        caption: str,
        hashtags: list[str],
        platform: str,
        engagement_rate: float = 0.0,
        view_count: int = 0,
    ) -> ReusableAsset:
        """Extract a packaging template asset from completed packaging output."""
        content = f"{caption}\n\n" + "\n".join(hashtags)
        asset = ReusableAsset(
            asset_type=ReusableAssetType.PACKAGING_TEMPLATE,
            name=f"Packaging: {caption[:50]}",
            description=f"Packaging template for {platform} from idea {idea_id}",
            content=content,
            source_idea_id=idea_id,
            source_run_id=run_id,
            source_brief_id=brief_id,
            source_stage="packaging",
            extraction_reason="Strong packaging performance",
            platform=platform,
            performance_score=engagement_rate * 100 if engagement_rate else 0.0,
            engagement_rate=engagement_rate,
            view_count=view_count,
        )
        self.add(asset)
        return asset

    def extract_from_angle(
        self,
        idea_id: str,
        run_id: str,
        brief_id: str,
        thesis: str,
        angle_id: str = "",
        engagement_rate: float = 0.0,
        view_count: int = 0,
    ) -> ReusableAsset:
        """Extract an angle/argument structure asset from completed angle output."""
        asset = ReusableAsset(
            asset_type=ReusableAssetType.ARGUMENT_STRUCTURE,
            name=f"Angle: {thesis[:50]}",
            description=f"Argument structure extracted from idea {idea_id}",
            content=thesis,
            content_yaml=angle_id,
            source_idea_id=idea_id,
            source_run_id=run_id,
            source_brief_id=brief_id,
            source_stage="generate_angles",
            extraction_reason="Winning angle structure",
            performance_score=engagement_rate * 100 if engagement_rate else 0.0,
            engagement_rate=engagement_rate,
            view_count=view_count,
        )
        self.add(asset)
        return asset
