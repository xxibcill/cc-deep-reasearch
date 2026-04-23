"""Tests for the _serialization helper module."""

from __future__ import annotations

from pydantic import BaseModel

from cc_deep_research.content_gen._serialization import model_list_to_json, model_to_json


class SimpleModel(BaseModel):
    name: str
    value: int


class NestedModel(BaseModel):
    simple: SimpleModel
    tags: list[str]


class TestModelToJson:
    """Tests for model_to_json()."""

    def test_serializes_basic_model(self) -> None:
        """model_to_json returns a JSON-compatible dict."""
        model = SimpleModel(name="test", value=42)
        result = model_to_json(model)
        assert result == {"name": "test", "value": 42}

    def test_serializes_nested_model(self) -> None:
        """model_to_json handles nested Pydantic models."""
        model = NestedModel(simple=SimpleModel(name="nested", value=1), tags=["a", "b"])
        result = model_to_json(model)
        assert result["simple"] == {"name": "nested", "value": 1}
        assert result["tags"] == ["a", "b"]

    def test_round_trips_through_json(self) -> None:
        """model_to_json output is valid JSON (can be serialized and deserialized)."""
        import json

        model = SimpleModel(name="roundtrip", value=99)
        result = model_to_json(model)
        # Should not raise
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed == {"name": "roundtrip", "value": 99}


class TestModelListToJson:
    """Tests for model_list_to_json()."""

    def test_serializes_list_of_models(self) -> None:
        """model_list_to_json serializes a list of Pydantic models."""
        models = [SimpleModel(name="a", value=1), SimpleModel(name="b", value=2)]
        result = model_list_to_json(models)
        assert result == [{"name": "a", "value": 1}, {"name": "b", "value": 2}]

    def test_handles_empty_list(self) -> None:
        """model_list_to_json handles an empty list."""
        result = model_list_to_json([])
        assert result == []
