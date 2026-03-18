"""Helper utilities for loading test fixtures."""

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def load_fixture(fixture_name: str) -> dict[str, Any]:
    """Load a JSON fixture file by name.

    Args:
        fixture_name: Name of the fixture file (with or without .json extension).

    Returns:
        Parsed JSON content as a dictionary.

    Raises:
        FileNotFoundError: If fixture file doesn't exist.
    """
    if not fixture_name.endswith(".json"):
        fixture_name += ".json"

    fixture_path = FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_name}")

    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def load_tavily_search_healthy() -> dict[str, Any]:
    """Load the healthy Tavily search response fixture."""
    return load_fixture("tavily_search_healthy")


def load_tavily_search_malformed() -> dict[str, Any]:
    """Load the malformed Tavily search response fixture."""
    return load_fixture("tavily_search_malformed")


def load_analysis_healthy() -> dict[str, Any]:
    """Load the healthy analysis response fixture."""
    return load_fixture("analysis_healthy")


def load_analysis_malformed() -> dict[str, Any]:
    """Load the malformed/partial analysis response fixture."""
    return load_fixture("analysis_malformed")


def load_analysis_cross_reference() -> dict[str, Any]:
    """Load the analysis fixture with cross-reference points."""
    return load_fixture("analysis_cross_reference")


def list_fixtures() -> list[str]:
    """List all available fixture files.

    Returns:
        List of fixture file names.
    """
    return sorted(f.name for f in FIXTURES_DIR.glob("*.json"))


__all__ = [
    "load_fixture",
    "load_tavily_search_healthy",
    "load_tavily_search_malformed",
    "load_analysis_healthy",
    "load_analysis_malformed",
    "load_analysis_cross_reference",
    "list_fixtures",
]
