"""Response serialization helpers for content-gen route handlers."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def model_to_json(model: BaseModel) -> dict[str, Any]:
    """Serialize a Pydantic model to a JSON-compatible dict.

    This is equivalent to json.loads(model.model_dump_json()) but avoids
    the intermediate string when you only need the dict.
    """
    return json.loads(model.model_dump_json())


def model_list_to_json(models: list[BaseModel]) -> list[dict[str, Any]]:
    """Serialize a list of Pydantic models to JSON-compatible dicts."""
    return [json.loads(m.model_dump_json()) for m in models]
