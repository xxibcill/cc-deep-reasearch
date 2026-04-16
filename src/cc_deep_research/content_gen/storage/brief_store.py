"""YAML persistence for managed opportunity briefs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from cc_deep_research.content_gen.models import ManagedBriefOutput, ManagedOpportunityBrief
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

if TYPE_CHECKING:
    from cc_deep_research.config import Config


class BriefStore:
    """Load and save :class:`ManagedBriefOutput` to a YAML file."""

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="brief_path",
            default_name="briefs.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> ManagedBriefOutput:
        """Load all managed briefs from disk, returning an empty output when missing."""
        if not self._path.exists():
            return ManagedBriefOutput()
        data = yaml.safe_load(self._path.read_text()) or {}
        return ManagedBriefOutput.model_validate(data)

    def save(self, output: ManagedBriefOutput) -> None:
        """Persist managed briefs to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = output.model_dump(mode="json", exclude_none=True)
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def update_brief(self, brief_id: str, patch: dict) -> ManagedOpportunityBrief | None:
        """Update a single brief and save. Returns the updated brief or None."""
        output = self.load()
        for brief in output.briefs:
            if brief.brief_id == brief_id:
                unsupported_fields = sorted(set(patch) - set(ManagedOpportunityBrief.model_fields))
                if unsupported_fields:
                    raise ValueError(
                        "Unsupported brief fields: " + ", ".join(unsupported_fields)
                    )
                merged = brief.model_dump(mode="python")
                merged.update(patch)
                updated = ManagedOpportunityBrief.model_validate(merged)
                output.briefs = [updated if b.brief_id == brief_id else b for b in output.briefs]
                self.save(output)
                return updated
        # brief_id not found — return None (caller should handle this case)
        return None
