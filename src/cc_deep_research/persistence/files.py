"""Crash-safe local file replacement helpers."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write text through a sibling temporary file and atomically replace it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def atomic_write_json(
    path: Path,
    data: Any,
    *,
    indent: int | None = 2,
    default: Callable[[Any], Any] | None = None,
) -> None:
    """Serialize JSON and atomically replace ``path``."""
    atomic_write_text(
        path,
        json.dumps(data, indent=indent, default=default),
        encoding="utf-8",
    )


def _fsync_directory(directory: Path) -> None:
    """Best-effort durability for the rename metadata."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


__all__ = ["atomic_write_json", "atomic_write_text"]
