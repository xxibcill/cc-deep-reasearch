"""Persistent history for standalone scripting runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cc_deep_research.content_gen.models import SavedScriptRun, ScriptingContext

_DEFAULT_DIR = Path.home() / ".config" / "cc-deep-research" / "scripts"


class ScriptingStore:
    """Load and save standalone scripting runs."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_DIR

    @property
    def path(self) -> Path:
        return self._path

    def save(self, ctx: ScriptingContext) -> SavedScriptRun:
        """Persist a scripting run and update latest pointers."""
        saved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        run_dir = self._path / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        script = self._extract_script(ctx)
        script_path = run_dir / "script.txt"
        context_path = run_dir / "context.json"
        script_path.write_text(script)
        context_path.write_text(ctx.model_dump_json(indent=2))

        record = SavedScriptRun(
            run_id=run_id,
            saved_at=saved_at,
            raw_idea=ctx.raw_idea,
            word_count=len(script.split()),
            script_path=str(script_path),
            context_path=str(context_path),
        )
        (run_dir / "metadata.json").write_text(record.model_dump_json(indent=2))

        self._path.mkdir(parents=True, exist_ok=True)
        (self._path / "latest.txt").write_text(script)
        (self._path / "latest.context.json").write_text(ctx.model_dump_json(indent=2))
        (self._path / "latest.json").write_text(record.model_dump_json(indent=2))
        return record

    def list_runs(self, *, limit: int | None = None) -> list[SavedScriptRun]:
        """Return saved runs, newest first."""
        if not self._path.exists():
            return []

        records: list[SavedScriptRun] = []
        for metadata_path in self._path.glob("*/metadata.json"):
            records.append(SavedScriptRun.model_validate_json(metadata_path.read_text()))

        records.sort(key=lambda record: record.saved_at, reverse=True)
        if limit is not None:
            return records[:limit]
        return records

    def latest(self) -> SavedScriptRun | None:
        """Return the latest saved run, if any."""
        latest_path = self._path / "latest.json"
        if latest_path.exists():
            return SavedScriptRun.model_validate_json(latest_path.read_text())
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None

    def get(self, run_id: str) -> SavedScriptRun | None:
        """Return a saved run by id."""
        metadata_path = self._path / run_id / "metadata.json"
        if not metadata_path.exists():
            return None
        return SavedScriptRun.model_validate_json(metadata_path.read_text())

    @staticmethod
    def _extract_script(ctx: ScriptingContext) -> str:
        if ctx.qc is not None and ctx.qc.final_script:
            return ctx.qc.final_script
        if ctx.tightened is not None and ctx.tightened.content:
            return ctx.tightened.content
        if ctx.draft is not None and ctx.draft.content:
            return ctx.draft.content
        return ""
