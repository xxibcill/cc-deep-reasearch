"""Route-facing API service for backlog HTTP workflows.

This service handles HTTP-level composition (request parsing, response shaping,
error classification) while delegating domain behavior to BacklogService.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config, load_config
from cc_deep_research.content_gen.backlog_service import BacklogService
from cc_deep_research.content_gen.models import BacklogItem
from cc_deep_research.content_gen.pipeline_run_service import DuplicateActiveItemError

if TYPE_CHECKING:
    from cc_deep_research.content_gen.pipeline_run_service import PipelineRunService

logger = logging.getLogger(__name__)


class BacklogApiError(Exception):
    """Base class for backlog API errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BacklogItemNotFoundError(BacklogApiError):
    """Raised when a backlog item does not exist."""

    def __init__(self, idea_id: str) -> None:
        super().__init__(f"Backlog item not found: {idea_id}", status_code=404)


class BacklogValidationError(BacklogApiError):
    """Raised when request validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class DuplicateActivePipelineError(BacklogApiError):
    """Raised when a backlog item is already in an active pipeline."""

    def __init__(self, pipeline_id: str) -> None:
        self.pipeline_id = pipeline_id
        super().__init__(
            f"Backlog item is already in an active pipeline: {pipeline_id}",
            status_code=409,
        )


@dataclass
class StartFromBacklogResult:
    """Result of starting a pipeline from a backlog item."""

    pipeline_id: str
    status: str
    idea_id: str
    from_stage: int = 4
    to_stage: int | None = None


class BacklogApiService:
    """API-level service for backlog HTTP request handling.

    This class handles HTTP-specific concerns:
    - Request validation and parsing
    - Response shaping (serialization)
    - Error classification and mapping
    - HTTP workflow composition

    Domain behavior is delegated to BacklogService.
    Pipeline start is delegated to PipelineRunService.
    """

    def __init__(
        self,
        config: Config | None = None,
        backlog_service: BacklogService | None = None,
        pipeline_service: PipelineRunService | None = None,
    ) -> None:
        self._config = config or load_config()
        self._backlog_service = backlog_service or BacklogService(self._config)
        self._pipeline_service = pipeline_service

    @property
    def path(self) -> Path:
        """Return the backlog store path."""
        return self._backlog_service.path

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def create_item(self, request_data: dict[str, Any]) -> BacklogItem:
        """Create a new backlog item.

        Args:
            request_data: Dict of item fields from request body.

        Returns:
            Created BacklogItem.

        Raises:
            BacklogValidationError: If validation fails.
        """
        try:
            return self._backlog_service.create_item(
                title=request_data.get("title", ""),
                one_line_summary=request_data.get("one_line_summary", ""),
                raw_idea=request_data.get("raw_idea", ""),
                constraints=request_data.get("constraints", ""),
                idea=request_data.get("idea", ""),
                category=request_data.get("category", ""),
                audience=request_data.get("audience", ""),
                persona_detail=request_data.get("persona_detail", ""),
                problem=request_data.get("problem", ""),
                emotional_driver=request_data.get("emotional_driver", ""),
                urgency_level=request_data.get("urgency_level", ""),
                source=request_data.get("source", ""),
                why_now=request_data.get("why_now", ""),
                hook=request_data.get("hook", ""),
                content_type=request_data.get("content_type", ""),
                format_duration=request_data.get("format_duration", ""),
                key_message=request_data.get("key_message", ""),
                call_to_action=request_data.get("call_to_action", ""),
                evidence=request_data.get("evidence", ""),
                proof_gap_note=request_data.get("proof_gap_note", ""),
                expertise_reason=request_data.get("expertise_reason", ""),
                genericity_risk=request_data.get("genericity_risk", ""),
                risk_level=request_data.get("risk_level", "medium"),
                source_theme=request_data.get("source_theme", ""),
                selection_reasoning=request_data.get("selection_reasoning", ""),
            )
        except ValueError as exc:
            raise BacklogValidationError(str(exc)) from exc

    def list_items(self) -> tuple[Path, list[BacklogItem]]:
        """List all backlog items.

        Returns:
            Tuple of (backlog_path, items).
        """
        backlog = self._backlog_service.load()
        return self.path, backlog.items

    def update_item(self, idea_id: str, patch: dict[str, Any]) -> BacklogItem:
        """Update a backlog item.

        Args:
            idea_id: ID of the item to update.
            patch: Fields to update.

        Returns:
            Updated BacklogItem.

        Raises:
            BacklogValidationError: If patch is invalid.
            BacklogItemNotFoundError: If item doesn't exist.
        """
        try:
            updated = self._backlog_service.update_item(idea_id, patch)
        except ValueError as exc:
            raise BacklogValidationError(str(exc)) from exc

        if updated is None:
            raise BacklogItemNotFoundError(idea_id)
        return updated

    def select_item(self, idea_id: str) -> BacklogItem:
        """Select a backlog item.

        Args:
            idea_id: ID of the item to select.

        Returns:
            Selected BacklogItem.

        Raises:
            BacklogItemNotFoundError: If item doesn't exist.
        """
        selected = self._backlog_service.select_item(idea_id)
        if selected is None:
            raise BacklogItemNotFoundError(idea_id)
        return selected

    def archive_item(self, idea_id: str) -> BacklogItem:
        """Archive a backlog item.

        Args:
            idea_id: ID of the item to archive.

        Returns:
            Archived BacklogItem.

        Raises:
            BacklogItemNotFoundError: If item doesn't exist.
        """
        archived = self._backlog_service.archive_item(idea_id)
        if archived is None:
            raise BacklogItemNotFoundError(idea_id)
        return archived

    def delete_item(self, idea_id: str) -> int:
        """Delete a backlog item.

        Args:
            idea_id: ID of the item to delete.

        Returns:
            Number of items deleted (1).

        Raises:
            BacklogItemNotFoundError: If item doesn't exist.
        """
        removed = self._backlog_service.delete_item(idea_id)
        if not removed:
            raise BacklogItemNotFoundError(idea_id)
        return 1

    def start_from_item(self, idea_id: str) -> StartFromBacklogResult:
        """Start pipeline preparation from a backlog item.

        Args:
            idea_id: ID of the backlog item.

        Returns:
            StartFromBacklogResult with pipeline details.

        Raises:
            BacklogItemNotFoundError: If item doesn't exist.
            DuplicateActivePipelineError: If item already in active pipeline.
        """
        if self._pipeline_service is None:
            raise BacklogApiError("Pipeline service not configured", status_code=500)

        backlog = self._backlog_service.load()
        item = next((i for i in backlog.items if i.idea_id == idea_id), None)
        if item is None:
            raise BacklogItemNotFoundError(idea_id)

        try:
            result = self._pipeline_service.start_from_backlog_item(item)
            return StartFromBacklogResult(
                pipeline_id=result.pipeline_id,
                status=result.status,
                idea_id=idea_id,
                from_stage=4,
                to_stage=result.to_stage,
            )
        except DuplicateActiveItemError as e:
            raise DuplicateActivePipelineError(e.pipeline_id) from e

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_item(item: BacklogItem) -> dict[str, Any]:
        """Serialize a BacklogItem to JSON-compatible dict."""
        return json.loads(item.model_dump_json())

    def serialize_list(self) -> dict[str, Any]:
        """Serialize the backlog list response.

        Returns:
            Dict with path and items list.
        """
        _, items = self.list_items()
        return {
            "path": str(self.path),
            "items": [self.serialize_item(item) for item in items],
        }
