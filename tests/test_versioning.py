from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ABOUT_PATH = REPO_ROOT / "src" / "cc_deep_research" / "__about__.py"
INIT_PATH = REPO_ROOT / "src" / "cc_deep_research" / "__init__.py"
SCRIPT_PATH = REPO_ROOT / "scripts" / "bump_version.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_init_reexports_package_version_metadata() -> None:
    init_text = INIT_PATH.read_text(encoding="utf-8")

    assert "from cc_deep_research.__about__ import __version__" in init_text
    assert '"__version__",' in init_text


def test_pyproject_uses_about_file_for_version() -> None:
    pyproject_data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject_data["project"]["dynamic"] == ["version"]
    assert pyproject_data["tool"]["hatch"]["version"]["path"] == "src/cc_deep_research/__about__.py"


def test_readme_and_changelog_track_current_version() -> None:
    about_module = load_module("cc_deep_research_about", ABOUT_PATH)
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert f"Current codebase version: `{about_module.__version__}`" in readme_text
    assert "## [Unreleased]" in changelog_text
    assert f"## [{about_module.__version__}]" in changelog_text


def test_release_helper_resolves_semantic_bumps() -> None:
    module = load_module("bump_version", SCRIPT_PATH)

    assert module.resolve_next_version("0.1.0", "patch") == "0.1.1"
    assert module.resolve_next_version("0.1.0", "minor") == "0.2.0"
    assert module.resolve_next_version("0.1.0", "major") == "1.0.0"
    assert module.resolve_next_version("0.1.0", "1.4.2") == "1.4.2"


def test_release_helper_promotes_unreleased_notes() -> None:
    module = load_module("bump_version", SCRIPT_PATH)
    changelog_text = """# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Track new report export metadata.

## [0.1.0] - 2026-03-11

### Added

- Initial tracked release.
"""

    updated = module.build_updated_changelog(changelog_text, "0.2.0", "2026-03-12")

    assert "## [Unreleased]" in updated
    assert "## [0.2.0] - 2026-03-12" in updated
    assert "- Track new report export metadata." in updated
    assert updated.index("## [Unreleased]") < updated.index("## [0.2.0] - 2026-03-12")
