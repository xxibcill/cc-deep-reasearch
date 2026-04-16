"""YAML persistence for derivative and reuse opportunities (P4-T2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import DerivativeOpportunity
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

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


class DerivativeOpportunityStore:
    """Load and save derivative and reuse opportunities to a YAML file.

    Provides controlled paths for:
    - Storing derivative opportunities extracted from approved arguments
    - Tracking reuse opportunities across publish and performance analysis
    - Feeding derivative opportunities back into the backlog without re-running idea selection

    P4-T2: Each approved draft records at least one reuse path or an explicit reason none exists.
    Derivative opportunities survive publish and performance analysis.
    """

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="derivative_opportunity_path",
            default_name="derivative_opportunities.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[DerivativeOpportunity]:
        """Load all stored derivative opportunities from disk."""
        if not self._path.exists():
            return []
        data = yaml.safe_load(self._path.read_text()) or {}
        opportunities_data = data.get("opportunities", [])
        return [DerivativeOpportunity.model_validate(opp) for opp in opportunities_data]

    def save(self, opportunities: list[DerivativeOpportunity]) -> None:
        """Persist derivative opportunities to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "opportunities": [_serialize_model_to_dict(opp) for opp in opportunities],
            "last_updated": _now_iso(),
        }
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def add_opportunity(self, opportunity: DerivativeOpportunity) -> None:
        """Add a single derivative opportunity and persist."""
        opportunities = self.load()
        opportunities.append(opportunity)
        self.save(opportunities)

    def add_opportunities(self, opportunities: list[DerivativeOpportunity]) -> None:
        """Add multiple derivative opportunities and persist."""
        existing = self.load()
        existing.extend(opportunities)
        self.save(existing)

    def get_by_source(self, source_idea_id: str) -> list[DerivativeOpportunity]:
        """Get all derivative opportunities derived from a specific source idea."""
        return [opp for opp in self.load() if opp.source_idea_id == source_idea_id]

    def get_by_status(self, status: str) -> list[DerivativeOpportunity]:
        """Get all derivative opportunities with a specific status."""
        return [opp for opp in self.load() if opp.status == status]

    def get_by_derivative_type(self, derivative_type: str) -> list[DerivativeOpportunity]:
        """Get all derivative opportunities of a specific type."""
        return [opp for opp in self.load() if opp.derivative_type == derivative_type]

    def update_status(self, idea_id: str, status: str) -> None:
        """Update the status of a derivative opportunity by its idea_id."""
        opportunities = self.load()
        updated = False
        for opp in opportunities:
            if opp.idea_id == idea_id:
                opp.status = status  # type: ignore[assignment]
                updated = True
        if updated:
            self.save(opportunities)

    def get_pending_for_backlog(self) -> list[DerivativeOpportunity]:
        """Get all pending derivative opportunities that could feed back to the backlog."""
        return [opp for opp in self.load() if opp.status == "pending"]
