#!/usr/bin/env python3
"""Bump the project version and promote the changelog's unreleased notes."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Final

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "src" / "cc_deep_research" / "__about__.py"
README_FILE = REPO_ROOT / "README.md"
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"

SEMVER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
)
VERSION_ASSIGNMENT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r'^__version__ = "(?P<version>[^"]+)"$',
    re.MULTILINE,
)
README_VERSION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"Current codebase version: `[^`]+`"
)
UNRELEASED_SECTION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?ms)^## \[Unreleased\]\n(?P<body>.*?)(?=^## \[[^\]]+\]|\Z)"
)
COMMENT_PATTERN: Final[re.Pattern[str]] = re.compile(r"<!--.*?-->", re.DOTALL)

UNRELEASED_TEMPLATE = (
    "## [Unreleased]\n\n"
    "<!-- Add Added/Changed/Fixed entries here before cutting a release. -->\n\n"
)
DEFAULT_RELEASE_BODY = "### Changed\n\n- No user-facing changes were recorded for this release."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bump the project version and roll the changelog forward."
    )
    parser.add_argument(
        "target",
        help="Next version: patch, minor, major, or an explicit semantic version such as 0.2.0.",
    )
    parser.add_argument(
        "--date",
        dest="release_date",
        default=date.today().isoformat(),
        help="Release date to write into CHANGELOG.md (default: today).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the resolved version without modifying files.",
    )
    return parser.parse_args()


def parse_semantic_version(version: str) -> tuple[int, int, int]:
    match = SEMVER_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(f"Invalid semantic version: {version}")
    return tuple(int(part) for part in match.groups())


def read_current_version() -> str:
    version_text = VERSION_FILE.read_text(encoding="utf-8")
    match = VERSION_ASSIGNMENT_PATTERN.search(version_text)
    if match is None:
        raise ValueError(f"Could not find __version__ assignment in {VERSION_FILE}")
    return match.group("version")


def resolve_next_version(current_version: str, target: str) -> str:
    if SEMVER_PATTERN.fullmatch(target):
        return target

    major, minor, patch = parse_semantic_version(current_version)
    increments = {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
    }
    if target not in increments:
        raise ValueError(
            "Target must be patch, minor, major, or an explicit semantic version."
        )
    return increments[target]


def update_version_text(version_text: str, new_version: str) -> str:
    if VERSION_ASSIGNMENT_PATTERN.search(version_text) is None:
        raise ValueError("Version file is missing the __version__ assignment.")
    return VERSION_ASSIGNMENT_PATTERN.sub(
        f'__version__ = "{new_version}"',
        version_text,
        count=1,
    )


def update_readme_text(readme_text: str, new_version: str) -> str:
    if README_VERSION_PATTERN.search(readme_text) is None:
        raise ValueError("README.md is missing the current codebase version line.")
    return README_VERSION_PATTERN.sub(
        f"Current codebase version: `{new_version}`",
        readme_text,
        count=1,
    )


def normalize_release_body(body: str) -> str:
    stripped_body = COMMENT_PATTERN.sub("", body).strip()
    if stripped_body:
        return stripped_body
    return DEFAULT_RELEASE_BODY


def build_updated_changelog(changelog_text: str, new_version: str, release_date: str) -> str:
    if f"## [{new_version}]" in changelog_text:
        raise ValueError(f"CHANGELOG.md already contains version {new_version}.")

    unreleased_match = UNRELEASED_SECTION_PATTERN.search(changelog_text)
    if unreleased_match is None:
        raise ValueError("CHANGELOG.md is missing an [Unreleased] section.")

    release_body = normalize_release_body(unreleased_match.group("body"))
    remaining_history = changelog_text[unreleased_match.end() :].lstrip("\n")
    release_section = f"## [{new_version}] - {release_date}\n\n{release_body}\n\n"
    return (
        f"{changelog_text[:unreleased_match.start()]}"
        f"{UNRELEASED_TEMPLATE}"
        f"{release_section}"
        f"{remaining_history}"
    )


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()

    current_version = read_current_version()
    next_version = resolve_next_version(current_version, args.target)
    if next_version == current_version:
        raise ValueError("New version must differ from the current version.")

    updated_version = update_version_text(
        VERSION_FILE.read_text(encoding="utf-8"),
        next_version,
    )
    updated_readme = update_readme_text(
        README_FILE.read_text(encoding="utf-8"),
        next_version,
    )
    updated_changelog = build_updated_changelog(
        CHANGELOG_FILE.read_text(encoding="utf-8"),
        next_version,
        args.release_date,
    )

    if args.dry_run:
        print(f"{current_version} -> {next_version}")
        return 0

    write_text(VERSION_FILE, updated_version)
    write_text(README_FILE, updated_readme)
    write_text(CHANGELOG_FILE, updated_changelog)

    print(f"Bumped version {current_version} -> {next_version}")
    print("Updated src/cc_deep_research/__about__.py, README.md, and CHANGELOG.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
