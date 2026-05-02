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


def load_text_fixture(fixture_name: str) -> str:
    """Load a text fixture file by name."""
    fixture_path = FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_name}")
    return fixture_path.read_text(encoding="utf-8")


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


def load_content_gen_pipeline_smoke() -> dict[str, Any]:
    """Load the fixture-backed content-gen pipeline smoke payload."""
    return load_fixture("content_gen_pipeline_smoke")


def load_content_gen_pipeline_context() -> dict[str, Any]:
    """Load the content-gen pipeline context fixture."""
    return load_fixture("content_gen_pipeline_context")


def load_content_gen_backlog_item() -> dict[str, Any]:
    """Load the content-gen backlog item fixture."""
    return load_fixture("content_gen_backlog_item")


def load_content_gen_scoring_output() -> dict[str, Any]:
    """Load the content-gen scoring output fixture."""
    return load_fixture("content_gen_scoring_output")


def load_content_gen_managed_brief() -> dict[str, Any]:
    """Load the content-gen managed brief fixture."""
    return load_fixture("content_gen_managed_brief")


def load_content_gen_scripting_result() -> dict[str, Any]:
    """Load the content-gen scripting result fixture."""
    return load_fixture("content_gen_scripting_result")


def load_content_gen_strategy_memory() -> dict[str, Any]:
    """Load the content-gen strategy memory fixture."""
    return load_fixture("content_gen_strategy_memory")


def load_content_gen_argument_map_happy() -> str:
    """Load the happy-path argument map fixture."""
    return load_text_fixture("content_gen_argument_map_happy")


def load_content_gen_argument_map_malformed() -> str:
    """Load the malformed argument map fixture."""
    return load_text_fixture("content_gen_argument_map_malformed")


def list_fixtures() -> list[str]:
    """List all available fixture files.

    Returns:
        List of fixture file names.
    """
    return sorted(
        f.name for f in FIXTURES_DIR.iterdir() if f.is_file() and f.suffix in {".json", ".txt"}
    )


__all__ = [
    "load_fixture",
    "load_text_fixture",
    "load_tavily_search_healthy",
    "load_tavily_search_malformed",
    "load_analysis_healthy",
    "load_analysis_malformed",
    "load_analysis_cross_reference",
    "load_content_gen_pipeline_smoke",
    "load_content_gen_pipeline_context",
    "load_content_gen_backlog_item",
    "load_content_gen_scoring_output",
    "load_content_gen_managed_brief",
    "load_content_gen_scripting_result",
    "load_content_gen_strategy_memory",
    "load_content_gen_argument_map_happy",
    "load_content_gen_argument_map_malformed",
    "list_fixtures",
]
