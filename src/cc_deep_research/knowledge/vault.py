"""Knowledge vault filesystem layout and path resolution."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from cc_deep_research.config import get_default_config_path


def _config_parent() -> Path:
    """Parent directory of the config file — our vault root."""
    return get_default_config_path().parent


# ---------------------------------------------------------------------------
# Top-level vault directories
# ---------------------------------------------------------------------------


def vault_root(config_path: Path | None = None) -> Path:
    """Root directory of the knowledge vault.

    When config_path is a file (e.g. config.yaml), the vault root is its parent / "knowledge".
    When config_path is a directory, the vault root is that directory / "knowledge".
    When config_path is None, falls back to the default config file's parent / "knowledge".
    """
    if config_path is not None:
        if config_path.is_dir():
            return config_path / "knowledge"
        return config_path.parent / "knowledge"
    return _config_parent() / "knowledge"


def raw_dir(config_path: Path | None = None) -> Path:
    """Directory for immutable raw artifacts."""
    return vault_root(config_path) / "raw"


def wiki_dir(config_path: Path | None = None) -> Path:
    """Directory for synthesized wiki pages."""
    return vault_root(config_path) / "wiki"


def graph_dir(config_path: Path | None = None) -> Path:
    """Directory for SQLite graph index and exports."""
    return vault_root(config_path) / "graph"


def schema_dir(config_path: Path | None = None) -> Path:
    """Directory for schema documentation."""
    return vault_root(config_path) / "schema"


# ---------------------------------------------------------------------------
# Wiki subdirectories
# ---------------------------------------------------------------------------


def wiki_index_path(config_path: Path | None = None) -> Path:
    """Path to the wiki index page."""
    return wiki_dir(config_path) / "index.md"


def wiki_log_path(config_path: Path | None = None) -> Path:
    """Path to the vault activity log."""
    return wiki_dir(config_path) / "log.md"


def concepts_dir(config_path: Path | None = None) -> Path:
    """Directory for concept pages."""
    return wiki_dir(config_path) / "concepts"


def entities_dir(config_path: Path | None = None) -> Path:
    """Directory for entity pages."""
    return wiki_dir(config_path) / "entities"


def claims_dir(config_path: Path | None = None) -> Path:
    """Directory for claim pages."""
    return wiki_dir(config_path) / "claims"


def questions_dir(config_path: Path | None = None) -> Path:
    """Directory for question pages."""
    return wiki_dir(config_path) / "questions"


def sessions_dir(config_path: Path | None = None) -> Path:
    """Directory for session summary pages."""
    return wiki_dir(config_path) / "sessions"


def sources_dir(config_path: Path | None = None) -> Path:
    """Directory for source pages."""
    return wiki_dir(config_path) / "sources"


# ---------------------------------------------------------------------------
# Graph paths
# ---------------------------------------------------------------------------


def graph_sqlite_path(config_path: Path | None = None) -> Path:
    """Path to the SQLite graph index."""
    return graph_dir(config_path) / "graph.sqlite"


def graph_export_path(config_path: Path | None = None) -> Path:
    """Path to the graph JSON export."""
    return graph_dir(config_path) / "exports" / "graph.json"


# ---------------------------------------------------------------------------
# Schema paths
# ---------------------------------------------------------------------------


def agents_md_path(config_path: Path | None = None) -> Path:
    """Path to the LLM editing rules documentation."""
    return schema_dir(config_path) / "AGENTS.md"


# ---------------------------------------------------------------------------
# Raw artifact paths
# ---------------------------------------------------------------------------


def raw_session_dir(session_id: str, config_path: Path | None = None) -> Path:
    """Directory for a session's raw artifacts."""
    return raw_dir(config_path) / "sessions" / session_id


def raw_source_file(
    session_id: str,
    source_id: str,
    kind: Literal["session", "report", "sources", "manifest"],
    config_path: Path | None = None,
) -> Path:
    """Path to a specific raw artifact file."""
    return raw_session_dir(session_id, config_path) / f"{kind}.json"


# ---------------------------------------------------------------------------
# Vault initialization
# ---------------------------------------------------------------------------

_REQUIRED_DIRS: list[tuple[Callable[[Path | None], Path], str]] = [
    (raw_dir, "raw/"),
    (wiki_dir, "wiki/"),
    (graph_dir, "graph/"),
    (schema_dir, "schema/"),
    (concepts_dir, "wiki/concepts/"),
    (entities_dir, "wiki/entities/"),
    (claims_dir, "wiki/claims/"),
    (questions_dir, "wiki/questions/"),
    (sessions_dir, "wiki/sessions/"),
    (sources_dir, "wiki/sources/"),
    (lambda cfg: graph_dir(cfg) / "exports", "graph/exports/"),
]

_SEED_FILES: list[tuple[Callable[[Path | None], Path], str]] = [
    (wiki_index_path, "index.md"),
    (wiki_log_path, "log.md"),
    (agents_md_path, "AGENTS.md"),
]


def _seed_content(name: str) -> str:
    """Return seed content for a given filename."""
    if name == "index.md":
        return """\
---
id: vault-index
title: Knowledge Vault Index
kind: wiki_page
status: stable
---

# Knowledge Vault Index

This vault stores synthesized research knowledge derived from research sessions.

## Structure

- `concepts/` — high-level concept pages
- `entities/` — named entity pages
- `claims/` — individual claim pages with source backing
- `questions/` — research question pages
- `sessions/` — research session summary pages
- `sources/` — source document pages

## Usage

Use the CLI to ingest sessions, run lint, and rebuild the graph index.
"""
    if name == "log.md":
        return """\
# Vault Activity Log

<!-- Append ingest and maintenance events below -->

"""
    if name == "AGENTS.md":
        return """\
# Agent Editing Rules

These rules govern how LLMs may edit wiki pages in this vault.

## Core Principles

1. **Never mutate files in `raw/`** — Raw artifacts are immutable.
2. **Preserve source links for claims** — Every claim must cite its source.
3. **Mark unsupported claims explicitly** — Use `status: needs_review` for claims without source backing.
4. **Append material changes to `wiki/log.md`** — Track all edits.
5. **Update `wiki/index.md` after page creation or major rename** — Keep the index current.

## Claim Guidelines

- Claims should be grounded in specific sources with URLs.
- Contradicting claims should be linked via the `contradicts` edge kind.
- Stale claims (for time-sensitive topics) should be marked `status: needs_review`.

## Page Naming

Pages use kebab-case IDs derived from normalized titles.
Session pages use the session ID as the filename stem.
"""
    return ""


def init_vault(
    config_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Path]:
    """Create all required vault directories and seed files.

    Returns a dict mapping logical name to the resolved path for each created item.
    Does nothing for items that already exist (idempotent).
    """
    created: dict[str, Path] = {}

    for dir_fn, label in _REQUIRED_DIRS:
        path = dir_fn(config_path)
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)
        created[f"dir:{label}"] = path

    for file_fn, filename in _SEED_FILES:
        path = file_fn(config_path)
        if not dry_run and not path.exists():
            content = _seed_content(filename)
            if content:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
        created[f"file:{filename}"] = path

    return created


__all__ = [
    "agents_md_path",
    "claims_dir",
    "concepts_dir",
    "entities_dir",
    "graph_dir",
    "graph_export_path",
    "graph_sqlite_path",
    "init_vault",
    "questions_dir",
    "raw_dir",
    "raw_session_dir",
    "raw_source_file",
    "schema_dir",
    "sessions_dir",
    "sources_dir",
    "vault_root",
    "wiki_dir",
    "wiki_index_path",
    "wiki_log_path",
]
