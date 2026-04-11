#!/usr/bin/env python3
"""
Script to auto-fix Phase 1 type errors.

This script fixes:
1. Missing type parameters for generic types (dict[...] without params)
2. Missing variable type annotations
3. Unused type:ignore comments
4. Untyped function definitions

Usage:
    python docs/scripts/auto_fix_phase1.py [--check] [--fix]
"""

import re
import sys
from pathlib import Path

# Files and their specific fixes for type-arg errors
TYPE_ARG_FIXES = {
    "src/cc_deep_research/content_gen/prompts/performance.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/storage/backlog_store.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/agents/packaging.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/agents/performance.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/agents/production.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/agents/research_pack.py": [
        (r"items: list", "items: list[str]"),  # line 105
        (r"config: dict", "config: dict[str, Any]"),  # line 155
    ],
    "src/cc_deep_research/content_gen/agents/visual.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/agents/angle.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/agents/backlog.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/orchestration/source_collection_parallel.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/web_server.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/cli.py": [
        (r"config: dict", "config: dict[str, Any]"),
    ],
    "src/cc_deep_research/content_gen/orchestrator.py": [
        (r"items: list", "items: list[Any]"),  # line 726
        (r"config: dict", "config: dict[str, Any]"),  # line 785
    ],
}

# Variable type annotation fixes
VAR_ANNOTATION_FIXES = {
    "src/cc_deep_research/post_validator.py": [
        (r"issues = \[\]", "issues: list[str] = []"),
        (r"warnings = \[\]", "warnings: list[str] = []"),
    ],
    "src/cc_deep_research/agents/report_refiner.py": [
        (r"result = \[\]", "result: list[str] = []"),
        (r"current_paragraph = \[\]", "current_paragraph: list[str] = []"),
    ],
    "src/cc_deep_research/monitoring.py": [
        (r"domains_by_family = \{\}", "domains_by_family: dict[str, list[str]] = {}"),
    ],
}

# Remove unused type:ignore comments
UNUSED_IGNORE_REMOVALS = {
    "src/cc_deep_research/content_gen/agents/backlog.py": [
        (r"# type: ignore\[unused-ignore\]\n", ""),
    ],
    "src/cc_deep_research/content_gen/agents/scripting.py": [
        (r"# type: ignore\[unused-ignore\]\n", ""),
    ],
    "src/cc_deep_research/content_gen/cli.py": [
        (r"# type: ignore\[unused-ignore\]\n", ""),
        (r"# type: ignore\[unused-ignore\]\n", ""),
    ],
}

# Function return type fixes
FUNCTION_RETURN_FIXES = {
    "src/cc_deep_research/telemetry/query.py": [
        (r"def _normalize_status\(status: str\)", "def _normalize_status(status: str) -> str"),
    ],
}


def process_file(filepath: Path, fixes: dict, check_only: bool = True) -> list[str]:
    """Apply fixes to a file and return list of changes made."""
    changes = []
    content = filepath.read_text()
    original = content

    for pattern, replacement in fixes.get(str(filepath.relative_to(Path.cwd())), []):
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            changes.append(f"  {pattern} -> {replacement}")
            content = new_content

    if not check_only and content != original:
        filepath.write_text(content)

    return changes


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-fix Phase 1 type errors")
    parser.add_argument("--check", action="store_true", help="Check fixes without applying")
    parser.add_argument("--fix", action="store_true", help="Apply fixes")
    args = parser.parse_args()

    if not args.check and not args.fix:
        print("Use --check to see what would be fixed, or --fix to apply changes")
        sys.exit(1)

    root = Path.cwd()
    total_changes = 0

    # Process type-arg fixes
    print("\n=== Type-Arg Fixes (missing generic type parameters) ===")
    for filepath_str, fixes in TYPE_ARG_FIXES.items():
        filepath = root / filepath_str
        if not filepath.exists():
            print(f"  SKIP: {filepath} (not found)")
            continue
        changes = process_file(filepath, {filepath_str: fixes}, check_only=not args.fix)
        if changes:
            print(f"\n{filepath}:")
            for c in changes:
                print(c)
            total_changes += len(changes)

    # Process var annotation fixes
    print("\n=== Variable Type Annotation Fixes ===")
    for filepath_str, fixes in VAR_ANNOTATION_FIXES.items():
        filepath = root / filepath_str
        if not filepath.exists():
            print(f"  SKIP: {filepath} (not found)")
            continue
        changes = process_file(filepath, {filepath_str: fixes}, check_only=not args.fix)
        if changes:
            print(f"\n{filepath}:")
            for c in changes:
                print(c)
            total_changes += len(changes)

    # Process unused ignore removals
    print("\n=== Remove Unused type:ignore Comments ===")
    for filepath_str, removes in UNUSED_IGNORE_REMOVALS.items():
        filepath = root / filepath_str
        if not filepath.exists():
            print(f"  SKIP: {filepath} (not found)")
            continue
        changes = process_file(filepath, {filepath_str: removes}, check_only=not args.fix)
        if changes:
            print(f"\n{filepath}:")
            for c in changes:
                print(c)
            total_changes += len(changes)

    # Process function return type fixes
    print("\n=== Function Return Type Fixes ===")
    for filepath_str, fixes in FUNCTION_RETURN_FIXES.items():
        filepath = root / filepath_str
        if not filepath.exists():
            print(f"  SKIP: {filepath} (not found)")
            continue
        changes = process_file(filepath, {filepath_str: fixes}, check_only=not args.fix)
        if changes:
            print(f"\n{filepath}:")
            for c in changes:
                print(c)
            total_changes += len(changes)

    if args.check:
        print(f"\n=== Would make {total_changes} changes ===")
    else:
        print(f"\n=== Made {total_changes} changes ===")
        print("\nRun `uv run mypy src/` to verify fixes")


if __name__ == "__main__":
    main()
