"""CLI commands for the content generation workflow."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import click

from cc_deep_research.config import Config

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import ScriptingContext

KNOWN_MODULES = frozenset({"scripting"})


def register_content_gen_commands(cli: click.Group) -> None:
    """Register content-gen commands with the main CLI group."""

    @cli.group()
    def content_gen() -> None:
        """Content generation workflow for short-form video."""

    @content_gen.command()
    @click.option("--idea", default=None, help="Raw video idea (required unless --from-file is given)")
    @click.option(
        "--from-file",
        type=click.Path(exists=True),
        default=None,
        help="Resume from saved context JSON",
    )
    @click.option(
        "--from-step",
        type=int,
        default=None,
        help="Step number to resume from (1-10)",
    )
    @click.option("-o", "--output", type=click.Path(), default=None, help="Save output to file")
    @click.option(
        "--save-context",
        is_flag=True,
        help="Save intermediate context as JSON",
    )
    @click.option("--quiet", is_flag=True, help="Only show final result")
    def script(
        idea: str | None,
        from_file: str | None,
        from_step: int | None,
        output: str | None,
        save_context: bool,
        quiet: bool,
    ) -> None:
        """Run the 10-step scripting pipeline for a short-form video."""
        config = Config()

        from cc_deep_research.content_gen.models import SCRIPTING_STEPS, ScriptingContext

        ctx: ScriptingContext | None = None
        step: int | None = None

        if from_file:
            ctx = ScriptingContext.model_validate_json(Path(from_file).read_text())
            step = from_step or 1
            if idea and idea != ctx.raw_idea:
                msg = "--idea does not match the saved context in --from-file"
                raise click.UsageError(msg)
            idea = idea or ctx.raw_idea
        else:
            if not idea:
                msg = "--idea is required unless --from-file is provided"
                raise click.UsageError(msg)
            step = from_step

        total = len(SCRIPTING_STEPS)

        if step is not None and not 1 <= step <= total:
            msg = f"--from-step must be between 1 and {total}"
            raise click.UsageError(msg)

        def progress(idx: int, label: str) -> None:
            if not quiet:
                click.echo(f"  Step {idx + 1}/{total}: {label}...")

        async def _run() -> ScriptingContext:
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)

            if ctx is not None and step is not None:
                if not quiet:
                    click.echo(f"Resuming from step {step}/{total}...")
                return await orch.run_scripting_from_step(ctx, step, progress_callback=progress)
            else:
                if not quiet:
                    click.echo(f'Scripting: "{idea}"')
                    click.echo(f"Running {total}-step pipeline...\n")
                return await orch.run_scripting(idea, progress_callback=progress)  # type: ignore[arg-type]

        try:
            result = asyncio.run(_run())
        except Exception:
            # Auto-save context on failure if a path is available.
            _auto_save_failed_context(ctx, output, quiet)
            raise

        # Output
        final = result.qc.final_script if result.qc else ""
        if not final:
            final = result.tightened.content if result.tightened else ""
        if not final:
            final = result.draft.content if result.draft else ""

        if not quiet:
            click.echo()
            if final:
                click.echo("=" * 60)
                click.echo("FINAL SCRIPT")
                click.echo("=" * 60)
                click.echo(final)
                click.echo("=" * 60)
                wc = len(final.split())
                click.echo(f"Word count: {wc}")
            else:
                click.echo("No script generated.")

        if output:
            Path(output).write_text(final)
            if not quiet:
                click.echo(f"\nSaved to: {output}")

        if save_context:
            ctx_path = output + ".context.json" if output else "scripting_context.json"
            Path(ctx_path).write_text(result.model_dump_json(indent=2))
            if not quiet:
                click.echo(f"Context saved to: {ctx_path}")

    @content_gen.command()
    @click.option("--idea", required=True, help="Raw video idea")
    @click.option("--steps", default=None, help="Comma-separated modules (default: scripting)")
    @click.option("-o", "--output", type=click.Path(), default=None)
    def pipeline(idea: str, steps: str | None, output: str | None) -> None:
        """Run multiple content gen modules in sequence."""
        config = Config()

        modules = [s.strip() for s in steps.split(",")] if steps else ["scripting"]

        unknown = [m for m in modules if m not in KNOWN_MODULES]
        if unknown:
            msg = f"Unknown module(s): {', '.join(unknown)}. Known modules: {', '.join(sorted(KNOWN_MODULES))}"
            raise click.UsageError(msg)

        async def _run() -> None:
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)

            if "scripting" in modules:
                click.echo(f'Running scripting module for: "{idea}"')
                result = await orch.run_scripting(idea)
                final = result.qc.final_script if result.qc else ""
                if not final and result.tightened:
                    final = result.tightened.content

                click.echo("\n" + "=" * 60)
                click.echo(final)
                click.echo("=" * 60)

                if output:
                    Path(output).write_text(final)
                    click.echo(f"Saved to: {output}")

        asyncio.run(_run())


def _auto_save_failed_context(
    ctx: ScriptingContext | None,
    output: str | None,
    quiet: bool,
) -> None:
    """Best-effort save of context when the pipeline crashes."""
    if ctx is None:
        return
    try:
        fallback_path = output + ".context.json" if output else "scripting_context_failed.json"
        Path(fallback_path).write_text(ctx.model_dump_json(indent=2))
        if not quiet:
            click.echo(f"\nPipeline failed. Partial context saved to: {fallback_path}", err=True)
    except Exception:
        pass  # best-effort; don't mask the original error


__all__ = ["register_content_gen_commands"]
